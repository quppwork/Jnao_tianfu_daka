#!/usr/bin/env python3
"""将 brain_power_audio_catalog.json 导入 content_item 表"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import get_session_factory, init_db  # noqa: E402
from app.services.catalog_import import (  # noqa: E402
    catalog_path,
    counts_match_expected,
    import_catalog,
    validate_catalog_counts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="导入脑力奥秘音频目录")
    parser.add_argument("--replace", action="store_true", help="清空后重新导入")
    parser.add_argument("--catalog", type=Path, default=None, help="JSON 路径")
    args = parser.parse_args()

    init_db()
    session = get_session_factory()()
    try:
        path = args.catalog or catalog_path()
        if not path.exists():
            print(f"[ERROR] 目录文件不存在: {path}")
            return 1
        inserted = import_catalog(session, path=path, replace=args.replace)
        counts = validate_catalog_counts(session)
        print(f"[OK] 本次新增 {inserted} 条，库内分布: {counts}")
        if counts_match_expected(session):
            print("[OK] 五天赋条数校验通过 (41 条)")
        else:
            print("[WARN] 条数与预期不一致，请检查 JSON")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
