"""只读/轻量回写 db_fz_jingnao：家长 AI 关联与测评结果。

同 RDS 实例、不同库：LEGACY_DATABASE_URL → db_fz_jingnao
  ys_dayu_parent_user.user_id  = ys_wx_member.id
  ys_dayu_parent_user.ai_user_id = jnao_daka.child_user.id
  ys_dayu_test_result.uid      = 通常同 wx_member.id（成人自测）
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy import text

from app.db.legacy_session import get_legacy_engine

logger = logging.getLogger("jnao.legacy_dayu")

# 劲脑侧：1=成人 2=儿童（与我们 talent_assessment.test_type 0/1 不同）
DAYU_TEST_ADULT = 1
DAYU_TEST_CHILD = 2


class LegacyDayuError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_engine():
    engine = get_legacy_engine()
    if engine is None:
        raise LegacyDayuError("LEGACY_DATABASE_URL 未配置，无法访问劲脑库", 503)
    return engine


def fetch_parent_user_by_wx_id(wx_user_id: int) -> dict[str, Any] | None:
    """按 ys_dayu_parent_user.user_id（= ys_wx_member.id）取一行。"""
    if wx_user_id < 1:
        return None
    engine = _require_engine()
    # 线上表可能无 talent/check_talent 列（天赋在 test_result），勿 SELECT 多余字段
    sql = text(
        """
        SELECT id, user_id, ai_user_id, ai_session_id, nickname, real_name, mobile,
               delete_time
        FROM ys_dayu_parent_user
        WHERE user_id = :uid AND delete_time = 0
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"uid": int(wx_user_id)}).mappings().first()
    except Exception as e:
        logger.exception("fetch_parent_user_by_wx_id failed")
        raise LegacyDayuError(f"读取 ys_dayu_parent_user 失败: {e}", 502) from e
    return dict(row) if row else None


def fetch_parent_user_by_ai_id(ai_user_id: int) -> dict[str, Any] | None:
    """按 ys_dayu_parent_user.ai_user_id（本系统 user_id）取一行。"""
    if ai_user_id < 1:
        return None
    engine = _require_engine()
    sql = text(
        """
        SELECT id, user_id, ai_user_id, ai_session_id, nickname, real_name, mobile,
               delete_time
        FROM ys_dayu_parent_user
        WHERE ai_user_id = :aid AND delete_time = 0
        ORDER BY id DESC
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"aid": int(ai_user_id)}).mappings().first()
    except Exception as e:
        logger.exception("fetch_parent_user_by_ai_id failed")
        raise LegacyDayuError(f"读取 ys_dayu_parent_user 失败: {e}", 502) from e
    return dict(row) if row else None


def fetch_test_result(
    *,
    wx_user_id: int,
    test_result_id: int | None = None,
    adult_only: bool = True,
) -> dict[str, Any] | None:
    """取测评结果；默认只要成人且 status=1。"""
    if wx_user_id < 1:
        return None
    engine = _require_engine()
    # 与线上一致：勿选可能不存在的 child_id 等扩展列
    if test_result_id and test_result_id > 0:
        sql = text(
            """
            SELECT id, uid, test_type, answer, property, talent, check_talent, results,
                   status, delete_time, create_time
            FROM ys_dayu_test_result
            WHERE id = :rid AND uid = :uid AND status = 1 AND delete_time = 0
            LIMIT 1
            """
        )
        params: dict[str, Any] = {"rid": int(test_result_id), "uid": int(wx_user_id)}
    else:
        type_clause = "AND test_type = :tt" if adult_only else ""
        sql = text(
            f"""
            SELECT id, uid, test_type, answer, property, talent, check_talent, results,
                   status, delete_time, create_time
            FROM ys_dayu_test_result
            WHERE uid = :uid AND status = 1 AND delete_time = 0 {type_clause}
            ORDER BY id DESC
            LIMIT 1
            """
        )
        params = {"uid": int(wx_user_id)}
        if adult_only:
            params["tt"] = DAYU_TEST_ADULT
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, params).mappings().first()
    except Exception as e:
        logger.exception("fetch_test_result failed")
        raise LegacyDayuError(f"读取 ys_dayu_test_result 失败: {e}", 502) from e
    return dict(row) if row else None


def update_parent_ai_link(
    *,
    wx_user_id: int,
    ai_user_id: int,
    access_token: str | None = None,
) -> None:
    """回写 ai_user_id / ai_session_id，供劲脑侧 iframe 拼参。"""
    if wx_user_id < 1 or ai_user_id < 1:
        raise LegacyDayuError("无效的用户关联参数")
    engine = _require_engine()
    now = int(time.time())
    token = (access_token or "").strip()
    if token:
        sql = text(
            """
            UPDATE ys_dayu_parent_user
            SET ai_user_id = :aid,
                ai_session_id = :tok,
                ai_session_time = :ts,
                update_time = :ts
            WHERE user_id = :uid AND delete_time = 0
            """
        )
        params = {
            "aid": int(ai_user_id),
            "tok": token[:512],
            "ts": now,
            "uid": int(wx_user_id),
        }
    else:
        sql = text(
            """
            UPDATE ys_dayu_parent_user
            SET ai_user_id = :aid, update_time = :ts
            WHERE user_id = :uid AND delete_time = 0
            """
        )
        params = {"aid": int(ai_user_id), "ts": now, "uid": int(wx_user_id)}
    with engine.begin() as conn:
        result = conn.execute(sql, params)
        if result.rowcount < 1:
            raise LegacyDayuError("未更新到家长行，请确认 ys_dayu_parent_user 存在", 404)
    logger.info(
        "legacy parent ai link wx_uid=%s ai_uid=%s token=%s",
        wx_user_id,
        ai_user_id,
        "yes" if token else "no",
    )


def parse_dayu_results_blob(raw: Any) -> dict[str, Any]:
    """ys_dayu_test_result.results → dict（WuDao JSON）。"""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    text_v = str(raw).strip()
    if not text_v:
        return {}
    try:
        data = json.loads(text_v)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def build_report_json_from_dayu_row(row: dict[str, Any]) -> dict[str, Any]:
    """拼成本系统 report_json（供 build_report_context / 天赋解答）。"""
    results = parse_dayu_results_blob(row.get("results"))
    talent = str(row.get("talent") or "").strip()
    check_talent = str(row.get("check_talent") or "").strip()
    report: dict[str, Any] = dict(results) if results else {}
    # 顶层字段优先用表列，保证切片能读到
    if talent:
        report["talent"] = talent
    if check_talent:
        report["check_talent"] = check_talent
    if results and "results" not in report:
        # 若整包就是 results 内层，包一层以对齐本站结构
        if any(k in results for k in ("Talent", "Ability", "Attribute", "State")):
            report["results"] = results
    # AttributeJs 有时在顶层或 Attribute 内
    if "AttributeJs" not in report and isinstance(results.get("AttributeJs"), (dict, str)):
        report["AttributeJs"] = results["AttributeJs"]
    return report
