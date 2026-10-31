#!/usr/bin/env python3
"""从 db_fz_jingnao 同步 ys_wx_member → jnao_daka.wx_member_snapshot（B 增量 / 全量）。

用法:
  python tools/sync_wx_member_snapshot.py              # 全量（凌晨 4 点）
  python tools/sync_wx_member_snapshot.py --incremental  # 增量（每 15 分钟）
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from app.db.session import get_session_factory
from app.services.wechat_auth_service import (
    sync_wx_members_from_legacy,
    sync_wx_members_incremental,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync wx_member_snapshot from legacy DB")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="增量同步（新 id / update_time 变更）；默认全量",
    )
    args = parser.parse_args()

    started = datetime.now()
    factory = get_session_factory()
    db = factory()
    try:
        if args.incremental:
            stats = sync_wx_members_incremental(db)
            label = "增量"
        else:
            stats = sync_wx_members_from_legacy(db)
            label = "全量"
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        db.close()

    elapsed = (datetime.now() - started).total_seconds()
    mode = stats.get("mode", "-")
    print(
        f"wx_member_snapshot {label}同步完成({mode}): 共 {stats['total']} 条, "
        f"有手机号 {stats['with_mobile']}, 无手机号 {stats['without_mobile']}, "
        f"耗时 {elapsed:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
