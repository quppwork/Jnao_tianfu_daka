#!/usr/bin/env python3
"""归档超期 QA / Guide 会话（默认保留 180 天，每孩子保留最近 N 条会话）"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(_BACKEND, ".env"), override=False)
load_dotenv(os.path.join(os.path.dirname(_BACKEND), ".env.production"), override=False)

from app.db.session import get_session_factory, init_db
from app.services.chat_archive_service import run_chat_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="归档超期 QA / Guide 聊天会话")
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("CHAT_ARCHIVE_RETAIN_DAYS", "180")),
        help="保留最近 N 天内的会话（默认 180）",
    )
    parser.add_argument(
        "--qa-keep-recent",
        type=int,
        default=int(os.getenv("CHAT_ARCHIVE_QA_KEEP_RECENT", "20")),
        help="每个孩子至少保留最近 N 条 QA 会话（默认 20）",
    )
    parser.add_argument(
        "--guide-keep-recent",
        type=int,
        default=int(os.getenv("CHAT_ARCHIVE_GUIDE_KEEP_RECENT", "10")),
        help="每个孩子至少保留最近 N 条 Guide 会话（默认 10）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("CHAT_ARCHIVE_BATCH_SIZE", "100")),
        help="单次最多处理会话数（默认 100）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入/删除")
    parser.add_argument("--qa-only", action="store_true", help="仅归档 QA")
    parser.add_argument("--guide-only", action="store_true", help="仅归档 Guide")
    args = parser.parse_args()

    if args.qa_only and args.guide_only:
        print(json.dumps({"ok": False, "error": "不能同时指定 --qa-only 与 --guide-only"}, ensure_ascii=False))
        return 2

    init_db()
    db = get_session_factory()()
    try:
        result = run_chat_archive(
            db,
            retain_days=args.days,
            qa_keep_recent=args.qa_keep_recent,
            guide_keep_recent=args.guide_keep_recent,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            include_qa=not args.guide_only,
            include_guide=not args.qa_only,
        )
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
