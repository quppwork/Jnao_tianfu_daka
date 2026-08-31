#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从百炼 ListIndexDocuments 刷新 backend/data/kb_registry.yaml 的 tags。

用法（在 backend 目录或项目根，需已配置 OSS/百炼 AK 与 workspace）:

  python scripts/sync_kb_registry_from_bailian.py
  python scripts/sync_kb_registry_from_bailian.py --dry-run

不下载全文；仅用文件名补充选库 tags。入库正文仍以百炼实时检索为准。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _load_dotenv() -> None:
    for candidate in (BACKEND / ".env", ROOT / ".env.production"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync kb_registry tags from Bailian")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = parser.parse_args()
    _load_dotenv()

    from app.services.kb_registry_sync import sync_registry_tags_from_bailian

    report = sync_registry_tags_from_bailian(dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
