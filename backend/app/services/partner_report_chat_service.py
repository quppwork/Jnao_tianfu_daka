"""合作方：把劲脑库测评同步到 jnao_daka，并签发「问大宇」嵌入参数。"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TalentAssessment
from app.services import auth_service, session_service
from app.services.legacy_dayu_service import (
    DAYU_TEST_ADULT,
    LegacyDayuError,
    build_report_json_from_dayu_row,
    fetch_parent_user_by_ai_id,
    fetch_parent_user_by_wx_id,
    fetch_test_result,
    update_parent_ai_link,
)
from app.services.parent_identity_service import find_login_parent_user
from app.services.sms_service import normalize_phone
from app.core.talent_mapping import resolve_talent_code, resolve_talent_tag

logger = logging.getLogger("jnao.partner_report_chat")

RECORD_PREFIX = "dayu_tr:"


def _site_domain() -> str:
    return (os.getenv("SITE_DOMAIN") or "https://jnaosoft.cn").rstrip("/")


def _dayu_record_id(test_result_id: int) -> str:
    return f"{RECORD_PREFIX}{int(test_result_id)}"


def _resolve_ai_user(
    db: Session,
    parent_row: dict[str, Any],
) -> ChildUser:
    """优先 ai_user_id；否则按手机号在本库找家长并回写关联。"""
    aid = int(parent_row.get("ai_user_id") or 0)
    if aid > 0:
        user = db.get(ChildUser, aid)
        if user and (user.role or "") == auth_service.ROLE_PARENT:
            return user
        if user:
            return user  # 容错：已指向本系统账号

    mobile = str(parent_row.get("mobile") or "").strip()
    if not mobile:
        raise HTTPException(
            409,
            "家长未同步 AI 账号（ai_user_id=0 且无手机号）。请先调用 /api/partner/jinnao/register-parent 并回写 ai_user_id",
        )
    try:
        phone = normalize_phone(mobile)
    except Exception as e:
        raise HTTPException(400, f"家长手机号无效: {e}") from e

    existing = find_login_parent_user(db, phone)
    if not existing:
        raise HTTPException(
            409,
            "本系统尚无该手机号家长账号。请先 /api/partner/jinnao/register-parent，再确保对话",
        )
    try:
        update_parent_ai_link(
            wx_user_id=int(parent_row["user_id"]),
            ai_user_id=int(existing.id),
            access_token=None,
        )
    except LegacyDayuError as e:
        logger.warning("backfill ai_user_id failed: %s", e.message)
    return existing


def upsert_assessment_from_dayu(
    db: Session,
    *,
    child_user_id: int,
    dayu_row: dict[str, Any],
) -> TalentAssessment:
    """把 ys_dayu_test_result 写入/更新 talent_assessment（成人 test_type=0）。"""
    tr_id = int(dayu_row["id"])
    partner_type = int(dayu_row.get("test_type") or 0)
    if partner_type == DAYU_TEST_ADULT:
        our_type = 0
    else:
        raise HTTPException(400, "仅支持成人测评进入报告对话（儿童报告请走孩子链路）")

    rid = _dayu_record_id(tr_id)
    report = build_report_json_from_dayu_row(dayu_row)
    talent_primary = str(dayu_row.get("talent") or report.get("talent") or "").strip() or None
    talent_code = resolve_talent_code(talent_primary) if talent_primary else None
    talent_tag = resolve_talent_tag(talent_code) if talent_code else None
    answer = str(dayu_row.get("answer") or "")[:35]

    row = db.scalar(
        select(TalentAssessment).where(
            TalentAssessment.jnao_record_id == rid,
            TalentAssessment.child_user_id == child_user_id,
        )
    )
    if row is None:
        row = TalentAssessment(
            child_user_id=child_user_id,
            jnao_record_id=rid,
            answer_bitstring=answer or None,
            test_type=our_type,
            talent_primary=talent_primary,
            talent_tag=talent_tag,
            talent_code=talent_code,
            report_json=report,
        )
        db.add(row)
    else:
        row.answer_bitstring = answer or row.answer_bitstring
        row.test_type = our_type
        row.talent_primary = talent_primary or row.talent_primary
        row.talent_tag = talent_tag or row.talent_tag
        row.talent_code = talent_code or row.talent_code
        row.report_json = report or row.report_json
    db.commit()
    db.refresh(row)
    return row


def prepare_assessment_for_dayu_test(
    db: Session,
    *,
    user_id: int,
    dayu_test_result_id: int,
    wx_user_id: int | None = None,
) -> dict[str, Any]:
    """登录用户打开嵌入页时：按 dayu 测评 id 同步本库报告（无需对方再调合作方新接口）。

    依赖：对方已用 register-parent 写好 ai_user_id，并把 JWT 放进 iframe 的 token。
    """
    if user_id < 1 or dayu_test_result_id < 1:
        raise HTTPException(400, "参数无效")

    user = db.get(ChildUser, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    wx_uid = int(wx_user_id or 0)
    if wx_uid < 1:
        try:
            parent_row = fetch_parent_user_by_ai_id(user_id)
        except LegacyDayuError as e:
            raise HTTPException(e.status_code, e.message) from e
        if not parent_row:
            raise HTTPException(
                404,
                "未找到 ys_dayu_parent_user.ai_user_id 关联，请确认已 register-parent 并回写 ai_user_id",
            )
        wx_uid = int(parent_row["user_id"])

    try:
        dayu_row = fetch_test_result(
            wx_user_id=wx_uid,
            test_result_id=dayu_test_result_id,
            adult_only=True,
        )
    except LegacyDayuError as e:
        raise HTTPException(e.status_code, e.message) from e
    if not dayu_row:
        raise HTTPException(404, "未找到该成人测评（ys_dayu_test_result）")

    assessment = upsert_assessment_from_dayu(
        db, child_user_id=user_id, dayu_row=dayu_row
    )
    return {
        "assessment_id": assessment.id,
        "talent_primary": assessment.talent_primary or "",
        "dayu_test_result_id": int(dayu_row["id"]),
        "user_id": user_id,
        "wx_user_id": wx_uid,
    }


def ensure_report_chat(
    db: Session,
    *,
    wx_user_id: int,
    test_result_id: int | None = None,
    device_label: str = "jinnao-embed",
) -> dict[str, Any]:
    """关联劲脑家长 + 测评 → 本库报告 + JWT，供 iframe 嵌入。"""
    if wx_user_id < 1:
        raise HTTPException(400, "wx_user_id 无效")

    try:
        parent_row = fetch_parent_user_by_wx_id(wx_user_id)
    except LegacyDayuError as e:
        raise HTTPException(e.status_code, e.message) from e
    if not parent_row:
        raise HTTPException(404, "ys_dayu_parent_user 无此 user_id（需先创建家长档案）")

    user = _resolve_ai_user(db, parent_row)

    try:
        dayu_row = fetch_test_result(
            wx_user_id=wx_user_id,
            test_result_id=test_result_id,
            adult_only=True,
        )
    except LegacyDayuError as e:
        raise HTTPException(e.status_code, e.message) from e
    if not dayu_row:
        raise HTTPException(404, "未找到可用的成人测评结果（ys_dayu_test_result）")

    assessment = upsert_assessment_from_dayu(
        db, child_user_id=user.id, dayu_row=dayu_row
    )
    token = session_service.issue_session(db, user, device_label=device_label[:100])

    try:
        update_parent_ai_link(
            wx_user_id=wx_user_id,
            ai_user_id=user.id,
            access_token=token,
        )
    except LegacyDayuError as e:
        logger.warning("write ai_session_id failed: %s", e.message)

    q = urlencode(
        {
            "assessment_id": assessment.id,
            "user_id": user.id,
            "token": token,
            **(
                {"talent": assessment.talent_primary}
                if assessment.talent_primary
                else {}
            ),
        }
    )
    embed_path = f"/static/dayu/html/report-talent-chat-embed.html?{q}"
    return {
        "user_id": user.id,
        "assessment_id": assessment.id,
        "access_token": token,
        "talent_primary": assessment.talent_primary or "",
        "dayu_test_result_id": int(dayu_row["id"]),
        "wx_user_id": wx_user_id,
        "embed_path": embed_path,
        "embed_url": f"{_site_domain()}{embed_path}",
    }
