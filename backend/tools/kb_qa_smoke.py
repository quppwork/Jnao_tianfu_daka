#!/usr/bin/env python3
"""百炼 knowledge/chat 冒烟（P0）。

用法（backend 目录）:
  python tools/kb_qa_smoke.py
  python tools/kb_qa_smoke.py --query "开口窍怎么练" --source video_practice
  python tools/kb_qa_smoke.py --query "学者天赋是什么" --source talent_doc
  python tools/kb_qa_smoke.py --list-sources
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Bailian knowledge/chat smoke")
    parser.add_argument("--query", default="开口窍怎么练")
    parser.add_argument("--source", default="video_practice", help="registry key")
    parser.add_argument("--aid", default="", help="override aid")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--list-sources", action="store_true")
    args = parser.parse_args()

    from app.services.kb_registry import get_kb_registry
    from app.services.bailian.knowledge_chat import knowledge_chat_sync
    from app.services.bailian import bailian_status

    print("=== bailian status ===")
    print(json.dumps(bailian_status(), ensure_ascii=False, indent=2))

    reg = get_kb_registry()
    print("\n=== kb sources ===")
    print(json.dumps(reg.list_sources(), ensure_ascii=False, indent=2))

    if args.list_sources:
        return 0

    src = reg.resolve(source_key=args.source, aid=args.aid or None)
    if not src:
        print(f"FAIL: unknown source {args.source!r}")
        return 1

    print(f"\n=== knowledge/chat source={src.key} aid={src.aid} ===")
    print(f"query: {args.query!r}")

    result = await asyncio.to_thread(
        knowledge_chat_sync,
        args.query,
        aid=src.aid,
        timeout=args.timeout,
    )
    if not result or not result.reply:
        print("FAIL: empty or error")
        return 1

    print(json.dumps(result.to_public_dict(), ensure_ascii=False, indent=2))
    print("\n--- reply ---\n")
    print(result.reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
