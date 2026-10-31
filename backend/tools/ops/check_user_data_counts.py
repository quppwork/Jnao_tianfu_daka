#!/usr/bin/env python3
"""检查 Jnao 用户相关表行数（线上/本地均可）。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from sqlalchemy import func, select

from app.db.legacy_session import get_legacy_engine
from app.db.models import (
    ChildUser,
    DakaMember,
    ParentChildBind,
    ParentWechatBind,
    TrainingPlan,
    UserSession,
    WxMemberSnapshot,
)
from app.db.session import get_database_url, get_session_factory, init_db
from app.services import auth_service


def main() -> int:
    init_db()
    url = get_database_url()
    host_hint = url.split("@")[-1].split("/")[0] if "@" in url else url
    db_name = url.rsplit("/", 1)[-1].split("?")[0] if "/" in url else "?"

    factory = get_session_factory()
    db = factory()
    try:
        counts = {
            "child_user": db.scalar(select(func.count()).select_from(ChildUser)) or 0,
            "parent_role": db.scalar(
                select(func.count()).select_from(ChildUser).where(ChildUser.role == auth_service.ROLE_PARENT)
            )
            or 0,
            "student_role": db.scalar(
                select(func.count()).select_from(ChildUser).where(ChildUser.role == auth_service.ROLE_STUDENT)
            )
            or 0,
            "parent_child_bind": db.scalar(select(func.count()).select_from(ParentChildBind)) or 0,
            "daka_member": db.scalar(select(func.count()).select_from(DakaMember)) or 0,
            "parent_wechat_bind": db.scalar(select(func.count()).select_from(ParentWechatBind)) or 0,
            "wx_member_snapshot": db.scalar(select(func.count()).select_from(WxMemberSnapshot)) or 0,
            "user_session": db.scalar(select(func.count()).select_from(UserSession)) or 0,
            "training_plan": db.scalar(select(func.count()).select_from(TrainingPlan)) or 0,
        }
        snap_mobile = (
            db.scalar(
                select(func.count()).select_from(WxMemberSnapshot).where(WxMemberSnapshot.mobile.isnot(None))
            )
            or 0
        )
    finally:
        db.close()

    print(f"database: {db_name} @ {host_hint}")
    for k, v in counts.items():
        print(f"{k}: {v}")
    print(f"wx_snapshot_with_mobile: {snap_mobile}")

    legacy = "未配置"
    if get_legacy_engine():
        legacy = "已配置"

    print(f"LEGACY_DATABASE_URL: {legacy}")

    wiped = (
        counts["parent_role"] <= 1
        and counts["student_role"] == 0
        and counts["parent_child_bind"] == 0
        and counts["daka_member"] == 0
        and counts["parent_wechat_bind"] == 0
        and counts["training_plan"] == 0
    )
    print(f"users_wiped_ok: {wiped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
