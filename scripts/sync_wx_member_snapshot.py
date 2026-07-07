#!/usr/bin/env python3
"""从 db_fz_jingnao.ys_wx_member 同步到 jnao_daka.wx_member_snapshot"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=False)
load_dotenv(ROOT / ".env.production", override=False)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.legacy_session import get_legacy_engine
from app.db.session import get_session_factory
from app.services.wechat_auth_service import upsert_snapshot


def main() -> int:
    legacy = get_legacy_engine()
    if not legacy:
        print("LEGACY_DATABASE_URL 未配置，跳过同步")
        return 1

    factory = get_session_factory()
    db: Session = factory()
    try:
        with legacy.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, openid, unionid, mobile, nickname, truename
                    FROM ys_wx_member
                    WHERE openid IS NOT NULL AND openid != ''
                    """
                )
            ).mappings().all()

        count = 0
        for row in rows:
            data = {
                "wx_member_id": row["id"],
                "openid": row["openid"],
                "unionid": row.get("unionid"),
                "mobile": row.get("mobile"),
                "nickname": row.get("nickname"),
                "truename": row.get("truename"),
            }
            upsert_snapshot(db, data)
            count += 1
        db.commit()
        print(f"已同步 {count} 条 wx_member_snapshot")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
