#!/usr/bin/env python3
"""同步 OSS 媒体目录 → content_item（生产 cron 用）

- 视频：扫描 shipin/ 新增入库
- 目录：从 /catalog_data 的 JSON 增量导入（音频 + 固定视频映射）

用法（容器内）:
  python tools/sync_oss_media.py
  python tools/sync_oss_media.py --scan-shipin
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

if not os.getenv("DATABASE_URL"):
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND, ".env"), override=False)
    _prod = os.path.join(_BACKEND, "..", ".env.production")
    if os.path.isfile(_prod):
        load_dotenv(_prod, override=False)

from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_all_xet_catalogs, import_from_oss, import_video_catalog
from app.services.oss_client import is_oss_configured


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 OSS 媒体到 content_item")
    parser.add_argument(
        "--scan-shipin",
        action="store_true",
        help="额外扫描 OSS shipin/ 目录，自动入库新视频",
    )
    args = parser.parse_args()

    if not is_oss_configured():
        print(json.dumps({"ok": False, "error": "OSS 未配置"}, ensure_ascii=False))
        raise SystemExit(1)

    init_db()
    db = get_session_factory()()
    try:
        audio = import_all_xet_catalogs(db, replace=False)
        videos_json = import_video_catalog(db, replace=False)
        shipin = {"scanned": 0, "new_video": 0, "skipped": 0}
        if args.scan_shipin:
            shipin = import_from_oss(db, prefix="shipin/", media_type="video", dry_run=False)
        out = {
            "ok": True,
            "audio_catalogs": audio,
            "video_catalog_json": videos_json,
            "oss_shipin_scan": {
                "scanned": shipin.get("scanned", 0),
                "new_video": shipin.get("new_video", 0),
                "skipped": shipin.get("skipped", 0),
            },
        }
        print(json.dumps(out, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
