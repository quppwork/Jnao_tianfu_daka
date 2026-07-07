#!/usr/bin/env python3
"""从 db_fz_jingnao.ys_wx_member 全量同步到 jnao_daka.wx_member_snapshot。

用法（服务器 Docker 内）:
  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \\
    python tools/sync_wx_member_snapshot.py

本地:
  python backend/tools/sync_wx_member_snapshot.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(ROOT / ".env.production", override=False)

from app.db.session import get_session_factory
from app.services.wechat_auth_service import sync_wx_members_from_legacy


def main() -> int:
    started = datetime.now()
    factory = get_session_factory()
    db = factory()
    try:
        stats = sync_wx_members_from_legacy(db)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        db.close()

    elapsed = (datetime.now() - started).total_seconds()
    print(
        f"wx_member_snapshot 同步完成: 共 {stats['total']} 条, "
        f"有手机号 {stats['with_mobile']}, 无手机号 {stats['without_mobile']}, "
        f"耗时 {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
