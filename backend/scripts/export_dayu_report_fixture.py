"""从劲脑另一库 ys_dayu_test_result 导出报告夹具，供 pytest / 线上回归用例。

用法（宝塔或本地，需能连 LEGACY / DAYU 库）：

  cd /data/wwwroot/jnao_daka/backend   # 或本机 backend
  # 加载 .env.production 里的老库连接后：
  python scripts/export_dayu_report_fixture.py \\
    --wx-user-id 10086 \\
    --test-result-id 90001 \\
    --out tests/fixtures/report_talent_dayu_sample.json

缺 --test-result-id 时取该用户最新成人测评。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export dayu test_result → report fixture")
    parser.add_argument("--wx-user-id", type=int, required=True)
    parser.add_argument("--test-result-id", type=int, default=0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tests/fixtures/report_talent_dayu_sample.json"),
    )
    args = parser.parse_args()

    # 保证能 import app.*
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app.services.legacy_dayu_service import (
        build_report_json_from_dayu_row,
        fetch_test_result,
    )
    from app.services.report_talent_context import build_report_context
    from app.services.report_talent_query import needs_report_context

    rid = int(args.test_result_id or 0) or None
    row = fetch_test_result(
        wx_user_id=int(args.wx_user_id),
        test_result_id=rid,
        adult_only=True,
    )
    if not row:
        print("未找到成人测评", file=sys.stderr)
        return 1

    # results 可能是 str，夹具里保持库内原样便于 upsert 复现
    dayu_row = {
        "id": int(row["id"]),
        "uid": int(row["uid"]),
        "test_type": int(row.get("test_type") or 0),
        "answer": str(row.get("answer") or "")[:35],
        "talent": str(row.get("talent") or ""),
        "check_talent": str(row.get("check_talent") or ""),
        "results": row.get("results")
        if isinstance(row.get("results"), str)
        else json.dumps(row.get("results") or {}, ensure_ascii=False),
    }
    report = build_report_json_from_dayu_row(dayu_row)
    summary = build_report_context(report, dayu_row.get("talent"))

    cases = [
        {
            "id": "generic_kb",
            "question": "五者天赋体系是什么",
            "needs_report": needs_report_context("五者天赋体系是什么"),
            "expect_query_has_report_block": False,
        },
        {
            "id": "generic_practice",
            "question": f"{dayu_row['talent'] or '思者'}怎么练",
            "needs_report": False,
            "expect_query_has_report_block": False,
        },
        {
            "id": "my_report",
            "question": "这份报告怎么看",
            "needs_report": True,
            "expect_query_has_report_block": True,
            "expect_fragment_contains": (dayu_row["talent"] or "报告")[:8],
        },
        {
            "id": "my_scores",
            "question": "我的五者分值怎样",
            "needs_report": True,
            "expect_query_has_report_block": True,
            "expect_fragment_contains": "五者分值",
        },
        {
            "id": "my_state",
            "question": "报告里当前状态是什么意思",
            "needs_report": True,
            "expect_query_has_report_block": True,
            "section_hint": "状态",
        },
    ]

    payload = {
        "_meta": {
            "source": "ys_dayu_test_result live export",
            "dayu_test_result_id": dayu_row["id"],
            "wx_user_id": dayu_row["uid"],
            "talent": dayu_row["talent"],
            "summary_preview": (summary or "")[:240],
        },
        "dayu_row": dayu_row,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out} id={dayu_row['id']} talent={dayu_row['talent']!r}")
    print(f"summary_chars={len(summary or '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
