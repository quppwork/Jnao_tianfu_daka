"""孩子学习辅助 — 检索别名 + 轻量 LLM（无写库）。"""

from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_CHILD = ("guide", "qa", "parent_guide")


async def search_materials(args: dict[str, Any]) -> dict[str, Any]:
    from app.harness.tools.retrieve_kb import retrieve_kb

    query = str(args.get("query") or args.get("q") or "").strip()
    return await retrieve_kb({"query": query, "timeout": args.get("timeout") or 25})


async def _llm(system: str, user: str, *, max_tokens: int = 280) -> dict[str, Any]:
    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        return {"ok": True, "skipped": True, "reason": "llm_not_configured"}
    text = await chat_completion(
        system_prompt=system,
        user_message=user,
        history=None,
        max_tokens=max_tokens,
    )
    return {"ok": True, "text": (text or "").strip()}


async def generate_socratic_hint(args: dict[str, Any]) -> dict[str, Any]:
    q = str(args.get("question") or args.get("query") or "").strip()
    if not q:
        return {"ok": False, "error": "question 不能为空"}
    out = await _llm(
        "你是教练。只给苏格拉底式提示，不要直接给答案。中文两三句。",
        q,
        max_tokens=160,
    )
    return out


async def evaluate_answer(args: dict[str, Any]) -> dict[str, Any]:
    q = str(args.get("question") or "").strip()
    a = str(args.get("answer") or "").strip()
    if not q or not a:
        return {"ok": False, "error": "需要 question 与 answer"}
    out = await _llm(
        "判断学生回答是否合理。只输出：结论（对/部分对/不对）+ 一句理由。不要完整解题。",
        f"题：{q}\n答：{a}",
        max_tokens=180,
    )
    return out


async def generate_quiz(args: dict[str, Any]) -> dict[str, Any]:
    material = str(args.get("material") or args.get("query") or "").strip()
    if not material:
        return {"ok": False, "error": "需要 material"}
    out = await _llm(
        "根据材料出 2 道短问答题，不要超纲。只输出题目。",
        material[:1500],
        max_tokens=280,
    )
    return out


def register() -> None:
    register_tool(
        ToolSpec(
            name="search_materials",
            description="在与引导页相同的知识库里做语义检索（Retrieve 切片，不直答）。",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=search_materials,
            profiles=_CHILD + ("consult",),
            plane="host",
            mcp_server="jnao-host",
        )
    )
    register_tool(
        ToolSpec(
            name="generate_socratic_hint",
            description="针对题目给提示、不给答案。",
            input_schema={
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
            handler=generate_socratic_hint,
            profiles=("guide", "qa"),
            plane="host",
            mcp_server="jnao-host",
        )
    )
    register_tool(
        ToolSpec(
            name="evaluate_answer",
            description="判断对错并给一句理由，不代替学科答疑完整讲解。",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
            },
            handler=evaluate_answer,
            profiles=("guide", "qa"),
            plane="host",
            mcp_server="jnao-host",
        )
    )
    register_tool(
        ToolSpec(
            name="generate_quiz",
            description="根据材料出少量问答题。",
            input_schema={
                "type": "object",
                "properties": {"material": {"type": "string"}},
                "required": ["material"],
            },
            handler=generate_quiz,
            profiles=("guide", "qa", "teacher"),
            plane="host",
            mcp_server="jnao-host",
        )
    )
