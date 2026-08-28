#!/usr/bin/env python3
"""将已有 child_user（role=parent）回填到 daka_member。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from sqlalchemy import select

from app.db.models import ChildUser
from app.db.session import get_session_factory
from app.services import auth_service
from app.services.member_registry_service import (
    CHANNEL_PASSWORD,
    CHANNEL_SMS,
    CHANNEL_WECHAT,
    find_daka_member_by_parent,
    register_daka_member_from_user,
)
from app.services.parent_profile_service import LOGIN_CHANNEL_WECHAT, get_login_channel


def main() -> int:
    factory = get_session_factory()
    db = factory()
    created = 0
    skipped = 0
    try:
        parents = db.scalars(
            select(ChildUser).where(
                ChildUser.role == auth_service.ROLE_PARENT,
                ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
            )
        ).all()
        for user in parents:
            if find_daka_member_by_parent(db, user.id):
                skipped += 1
                continue
            channel = CHANNEL_WECHAT if get_login_channel(user) == LOGIN_CHANNEL_WECHAT else CHANNEL_SMS
            if user.password_hash and channel != CHANNEL_WECHAT:
                channel = CHANNEL_PASSWORD
            register_daka_member_from_user(db, user, register_channel=channel)
            created += 1
        db.commit()
    finally:
        db.close()
    print(f"daka_member 回填完成: 新增 {created}，已存在跳过 {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
