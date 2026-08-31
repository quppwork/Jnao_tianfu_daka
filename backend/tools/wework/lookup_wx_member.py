#!/usr/bin/env python3
"""跨库查询微信会员：老库 ys_wx_member + Jnao snapshot / daka_member / wechat_bind。

用法:
  python -m tools.lookup_wx_member --phone 19805031756
  python -m tools.lookup_wx_member --openid oXXXX
  python -m tools.lookup_wx_member --phone 19805031756 --openid oXXXX
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from sqlalchemy import select

from app.db.legacy_session import get_legacy_engine
from app.db.models import ChildUser, DakaMember, ParentWechatBind, WxMemberSnapshot
from app.db.session import get_session_factory
from app.services.wechat_auth_service import (
    fetch_legacy_member,
    fetch_legacy_member_by_mobile,
)


def _dump(label: str, data: dict | None) -> None:
    print(f"\n=== {label} ===")
    if not data:
        print("(无记录)")
        return
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="查询微信会员在老库与 Jnao 的对应关系")
    parser.add_argument("--phone", help="手机号，如 19805031756")
    parser.add_argument("--openid", help="微信 openid")
    args = parser.parse_args()
    if not args.phone and not args.openid:
        parser.error("请指定 --phone 和/或 --openid")

    legacy_url = get_legacy_engine()
    print(f"LEGACY_DATABASE_URL: {'已配置' if legacy_url else '未配置（无法查老库）'}")

    if args.openid:
        _dump("老库 ys_wx_member (by openid)", fetch_legacy_member(args.openid))
    if args.phone:
        _dump("老库 ys_wx_member (by mobile)", fetch_legacy_member_by_mobile(args.phone))

    factory = get_session_factory()
    with factory() as db:
        if args.phone:
            phone = args.phone.strip()
            users = list(
                db.scalars(
                    select(ChildUser).where(
                        ChildUser.parent_phone == phone,
                        ChildUser.role == "parent",
                    )
                ).all()
            )
            _dump(
                "Jnao child_user (parent)",
                [{"id": u.id, "phone": u.parent_phone, "nickname": u.nickname, "status": u.account_status} for u in users]
                or None,
            )
            dm = db.scalar(select(DakaMember).where(DakaMember.mobile == phone))
            _dump(
                "Jnao daka_member",
                {
                    "parent_id": dm.parent_id,
                    "mobile": dm.mobile,
                    "openid": dm.openid,
                    "legacy_wx_member_id": dm.legacy_wx_member_id,
                    "legacy_matched": dm.legacy_matched,
                }
                if dm
                else None,
            )
            snaps = list(
                db.scalars(select(WxMemberSnapshot).where(WxMemberSnapshot.mobile == phone)).all()
            )
            _dump(
                "Jnao wx_member_snapshot (by mobile)",
                [
                    {
                        "wx_member_id": s.wx_member_id,
                        "openid": s.openid[:16] + "…" if s.openid and len(s.openid) > 16 else s.openid,
                        "mobile": s.mobile,
                        "truename": s.truename,
                    }
                    for s in snaps
                ]
                or None,
            )

        if args.openid:
            oid = args.openid.strip()
            snap = db.scalar(select(WxMemberSnapshot).where(WxMemberSnapshot.openid == oid))
            _dump(
                "Jnao wx_member_snapshot (by openid)",
                {
                    "wx_member_id": snap.wx_member_id,
                    "mobile": snap.mobile,
                    "truename": snap.truename,
                    "nickname": snap.nickname,
                }
                if snap
                else None,
            )
            dm2 = db.scalar(select(DakaMember).where(DakaMember.openid == oid))
            _dump(
                "Jnao daka_member (by openid)",
                {
                    "parent_id": dm2.parent_id,
                    "mobile": dm2.mobile,
                    "openid": dm2.openid,
                }
                if dm2
                else None,
            )
            bind = db.scalar(select(ParentWechatBind).where(ParentWechatBind.openid == oid))
            _dump(
                "Jnao parent_wechat_bind",
                {"parent_id": bind.parent_id, "wx_member_id": bind.wx_member_id}
                if bind
                else None,
            )

    print("\n字段对齐说明:")
    print("  老库 ys_wx_member: id, openid, unionid, mobile, nickname, truename")
    print("  Jnao wx_member_snapshot: wx_member_id←id, openid, unionid, mobile, nickname, truename")
    print("  Jnao daka_member: parent_id, mobile, openid, legacy_wx_member_id←id, legacy_matched")
    print("  Jnao parent_wechat_bind: parent_id, openid, unionid, wx_member_id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
