"""业务入口：所有 Agent 的模型+工具循环都走 run_agent。

会话表仍分域（guide_session / qa_session / consult_* / academy room）。
产品闸门（答疑学科、作业跳转、学院选角）留在各 facade，不进内核。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.harness.agent_state import AgentState
from app.harness.context import ToolContext
from app.harness.loop import iter_agent, run_agent
from app.harness.types import ToolResult


def _trace_rag(trace: list[dict[str, Any]]) -> bool:
    names = {"retrieve_kb", "retrieve_qa_kb", "retrieve_qa_legacy"}
    return any(t.get("name") in names and t.get("ok") for t in (trace or []))


def _public_turn(state: AgentState, profile: str) -> dict[str, Any]:
    return {
        "reply": (state.reply or "").strip(),
        "status": state.status,
        "tools_used": list(state.tool_trace or []),
        "rag_used": _trace_rag(state.tool_trace),
        "thread_id": state.thread_id,
        "pending_approvals": [p.to_dict() for p in state.pending_approvals],
        "profile": profile,
        "llm_calls": int((state.metadata or {}).get("llm_calls") or 0),
    }


async def run_profile_turn(
    profile: str,
    user_message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    system_extra: str = "",
    system_override: str | None = None,
    max_steps: int = 6,
    thread_id: str | None = None,
    model: Any | None = None,
    allow_tools: bool = True,
) -> dict[str, Any]:
    """一轮：system(+extra) → model → tools → reply。每轮 fresh，不复用内存 checkpoint。"""
    state = await run_agent(
        profile=profile,
        user_message=user_message,
        thread_id=thread_id,
        history=history,
        ctx=ctx,
        model=model,
        max_steps=max_steps,
        system_extra=system_extra or None,
        system_override=system_override,
        fresh=True,
        allow_tools=allow_tools,
    )
    return _public_turn(state, profile)


async def run_profile_turn_stream(
    profile: str,
    user_message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    system_extra: str = "",
    system_override: str | None = None,
    max_steps: int = 6,
    thread_id: str | None = None,
    model: Any | None = None,
    allow_tools: bool = False,
) -> AsyncIterator[tuple[str, Any]]:
    """流式：('token', str) … ('done', turn_dict)。闸门仍在 facade。"""
    async for kind, payload in iter_agent(
        profile=profile,
        user_message=user_message,
        thread_id=thread_id,
        history=history,
        ctx=ctx,
        model=model,
        max_steps=max_steps,
        system_extra=system_extra or None,
        system_override=system_override,
        fresh=True,
        allow_tools=allow_tools,
    ):
        if kind == "token":
            text = str(payload or "")
            if text.startswith("[ERROR]"):
                yield ("error", text)
                return
            yield ("token", text)
        elif kind == "done":
            yield ("done", _public_turn(payload, profile))


def tool_result_brief(result: ToolResult | None) -> dict[str, Any]:
    if result is None:
        return {"ok": False}
    return result.to_audit() | {"data": result.data}
