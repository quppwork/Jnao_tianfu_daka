#!/usr/bin/env python3
"""管理员恢复已移出/硬删家长（本地或容器内执行）。

示例:
  python -m tools.restore_parent --phone 19805031756 --nickname qupp
"""

from __future__ import annotations

import argparse
import sys

from app.db.session import SessionLocal
from app.services import admin_service, auth_service


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复已移出家长账号")
    parser.add_argument("--phone", help="家长手机号")
    parser.add_argument("--nickname", help="家长昵称")
    parser.add_argument("--admin-id", type=int, help="管理员 child_user id（默认取首个 active admin）")
    args = parser.parse_args()
    if not args.phone and not args.nickname:
        parser.error("至少提供 --phone 或 --nickname")

    db = SessionLocal()
    try:
        admin_id = args.admin_id
        if not admin_id:
            from sqlalchemy import select
            from app.db.models import ChildUser

            admin = db.scalars(
                select(ChildUser).where(
                    ChildUser.role == auth_service.ROLE_ADMIN,
                    ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
                )
            ).first()
            if not admin:
                print("未找到可用管理员账号", file=sys.stderr)
                return 1
            admin_id = admin.id

        data = admin_service.restore_parent_by_lookup(
            db, admin_id, phone=args.phone, nickname=args.nickname
        )
        print(f"已恢复家长 id={data['id']} {data['nickname']} {data['parent_phone']}")
        return 0
    except Exception as e:
        print(f"恢复失败: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
