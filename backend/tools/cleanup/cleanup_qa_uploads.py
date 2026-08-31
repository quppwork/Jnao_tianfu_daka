#!/usr/bin/env python3
"""清理过期学科答疑拍图（/app/data/qa_uploads，默认保留 30 天）"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)

UPLOAD_ROOT = Path(_BACKEND) / "data" / "qa_uploads"


def main() -> int:
    parser = argparse.ArgumentParser(description="清理过期 QA 拍图文件")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("QA_UPLOAD_RETAIN_DAYS", "30")),
        help="保留最近 N 天（默认 30）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不删除")
    args = parser.parse_args()

    retain_days = max(1, args.days)
    cutoff = time.time() - retain_days * 86400
    root = UPLOAD_ROOT

    scanned = 0
    deleted = 0
    freed = 0
    errors: list[str] = []

    if not root.is_dir():
        print(json.dumps({"ok": True, "scanned": 0, "deleted": 0, "freed_bytes": 0, "note": "目录不存在"}, ensure_ascii=False))
        return 0

    for path in root.iterdir():
        if not path.is_file():
            continue
        scanned += 1
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if mtime >= cutoff:
            continue
        size = path.stat().st_size
        if args.dry_run:
            deleted += 1
            freed += size
            continue
        try:
            path.unlink()
            deleted += 1
            freed += size
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")

    out = {
        "ok": len(errors) == 0,
        "dry_run": args.dry_run,
        "retain_days": retain_days,
        "root": str(root),
        "scanned": scanned,
        "deleted": deleted,
        "freed_bytes": freed,
        "errors": errors[:20],
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
