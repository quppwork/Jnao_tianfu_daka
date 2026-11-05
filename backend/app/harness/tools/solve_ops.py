"""拍题解答 Tools：search_question_bank / symbolic_verify。

OCR 已收敛到 harness/tools/ocr_ops.py（MCP jnao-host · ocr_extract）。
"""

from __future__ import annotations

import os
import re
from typing import Any

from app.harness.llm_catalog import SOLVE_PROFILE_NAMES
from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_SOLVE = tuple(SOLVE_PROFILE_NAMES)

_DEMO_BANK: list[dict[str, Any]] = [
    {
        "keywords": ("1+1", "一加一"),
        "answer": "2",
        "steps": ["两数相加：1+1=2。"],
        "knowledge_points": ["整数加法"],
        "source": "demo_bank",
    },
    {
        "keywords": ("勾股", "直角三角形", "a²+b²"),
        "answer": "直角三角形两直角边平方和等于斜边平方：a²+b²=c²。",
        "steps": ["识别直角三角形", "套用勾股定理", "代入求解"],
        "knowledge_points": ["勾股定理"],
        "source": "demo_bank",
    },
]


def xkw_configured() -> bool:
    key = (os.getenv("XKW_API_KEY") or "").strip()
    return bool(key) and not key.startswith("your-")


async def search_question_bank(args: dict[str, Any]) -> dict[str, Any]:
    """学科网开放平台预留；未配置时走本地演示题库。"""
    query = str(args.get("query") or args.get("text") or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空", "hit": False}

    if xkw_configured():
        return {
            "ok": True,
            "hit": False,
            "provider": "xkw",
            "note": "XKW_API_KEY 已配置，开放平台对接待补全；本次未命中，走 RAG/LLM。",
        }

    qlow = query.lower()
    for row in _DEMO_BANK:
        if any(k.lower() in qlow or k in query for k in row["keywords"]):
            return {
                "ok": True,
                "hit": True,
                "provider": "demo_bank",
                "mock": True,
                "answer": row["answer"],
                "steps": list(row["steps"]),
                "knowledge_points": list(row["knowledge_points"]),
                "source": row["source"],
            }
    return {
        "ok": True,
        "hit": False,
        "provider": "demo_bank",
        "mock": True,
    }


def symbolic_verify(args: dict[str, Any]) -> dict[str, Any]:
    """SymPy 校验；未安装时返回 soft-fail。"""
    expression = str(args.get("expression") or "").strip()
    claimed = str(args.get("claimed_result") or "").strip()
    if not expression:
        return {"ok": False, "verified": False, "error": "expression 不能为空"}

    expr = expression.replace("$", "").replace("\\", "")
    expr = re.sub(r"\s+", "", expr)
    claim = claimed.replace("$", "").replace("\\", "")
    claim = re.sub(r"\s+", "", claim)

    try:
        import sympy
    except ImportError:
        return {
            "ok": True,
            "verified": None,
            "skipped": True,
            "reason": "sympy_not_installed",
            "hint": "pip install sympy",
        }

    try:
        left = sympy.sympify(expr)
        if claim:
            right = sympy.sympify(claim)
            diff = sympy.simplify(left - right)
            verified = diff == 0
            return {
                "ok": True,
                "verified": bool(verified),
                "actual_result": str(sympy.simplify(left)),
            }
        return {
            "ok": True,
            "verified": None,
            "actual_result": str(sympy.simplify(left)),
            "note": "未提供 claimed_result，仅返回化简结果",
        }
    except Exception as e:
        return {"ok": True, "verified": False, "error": str(e)[:200]}


def register() -> None:
    register_tool(
        ToolSpec(
            name="search_question_bank",
            description="题库搜题（学科网预留；未配置时演示库）。命中则直接标准解析。",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "text": {"type": "string"},
                    "subject": {"type": "string"},
                },
                "additionalProperties": False,
            },
            handler=search_question_bank,
            permission="readonly",
            profiles=_SOLVE,
            plane="host",
            mcp_server="jnao-host",
        )
    )
    register_tool(
        ToolSpec(
            name="symbolic_verify",
            description="用 SymPy 验证理科表达式与声称结果是否一致。",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                    "claimed_result": {"type": "string"},
                },
                "required": ["expression"],
                "additionalProperties": False,
            },
            handler=symbolic_verify,
            permission="readonly",
            profiles=("solve_science", "harness"),
            plane="host",
            mcp_server="jnao-host",
        )
    )
