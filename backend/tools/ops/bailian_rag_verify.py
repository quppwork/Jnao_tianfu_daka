#!/usr/bin/env python3
"""验证百炼完整 RAG：配置 → ListIndices → Retrieve（可选 Search）。

用法（在 backend 目录）:
  python tools/bailian_rag_verify.py
  python tools/bailian_rag_verify.py --query "学者天赋是什么"
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
    parser = argparse.ArgumentParser(description="Bailian RAG verify")
    parser.add_argument("--query", default="学者天赋是什么")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    from app.services.bailian import bailian_status, rag_query
    from app.services.bailian.search import list_indices_sync

    status = bailian_status()
    print("=== status ===")
    print(json.dumps(status, ensure_ascii=False, indent=2))

    print("\n=== list indices ===")
    try:
        indices = list_indices_sync()
        print(json.dumps(indices, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(f"list failed: {e}")

    if args.list_only:
        return 0

    print(f"\n=== rag_query: {args.query!r} ===")
    # 验证脚本不强制 GUIDE_RAG_ENABLED，直接跑流水线
    result = await rag_query(args.query, require_guide_enabled=False)
    if result is None:
        print("FAIL: no result (check AK / workspace / index_id)")
        return 1
    print(json.dumps(result.to_public_dict(), ensure_ascii=False, indent=2))
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
