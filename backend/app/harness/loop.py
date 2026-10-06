"""统一编排循环 — 主流 Agent：model → tool_calls → execute/interrupt → 再 model。

形态对齐：
- OpenAI Agents SDK Runner：直到无 tool_calls 或 hit max_turns
- LangGraph ToolNode + interrupt：confirm 工具暂停，resume 后续跑
- Anthropic tool_use 环：assistant + tool 结果写回 messages

不做跨 Guide/QA/学院的超级编排；产品闸门通过 GateHook 挂在循环前。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.harness.agent_state import AgentState, PendingApproval
from app.harness.audit import audit_loop
from app.harness.catalog import aggregated_tools
from app.harness.checkpoint import load_state, save_state
from app.harness.context import ToolContext
from app.harness.llm import profile_system
from app.harness.memory import window_for_model
from app.harness.openai_tools import openai_tools_for_profile, parse_tool_calls
from app.harness.policy import check_tool, check_user_message
from app.harness.registry import get_tool
from app.harness.runtime import call_tool
from app.harness.trace import emit as emit_trace

logger = logging.getLogger("jnao.harness.loop")

GateHook = Callable[[AgentState], Awaitable[AgentState | None] | AgentState | None]


class ModelAdapter(Protocol):
    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        ...


_GATES: dict[str, list[GateHook]] = {}



def register_gate(profile: str, hook: GateHook) -> None:
    _GATES.setdefault(profile, []).append(hook)


def clear_gates() -> None:
    _GATES.clear()


class DeepSeekAdapter:
    def __init__(self, profile: str = "harness") -> None:
        self.profile = profile

    def _cfg(self) -> dict[str, Any]:
        from app.harness.llm import PROFILES

        return PROFILES.get(self.profile) or PROFILES["harness"]

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        from app.services.doubao_client import chat_completion_message, is_configured

        if not is_configured():
            return {"role": "assistant", "content": "模型未配置，请稍后重试。"}
        cfg = self._cfg()
        msg = await chat_completion_message(
            messages=messages,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            max_tokens=int(cfg.get("max_tokens") or 700),
            timeout=float(cfg.get("timeout") or 45),
            feature=f"harness.{self.profile}",
        )
        if not isinstance(msg, dict):
            return {"role": "assistant", "content": "暂时无法生成回复。"}
        msg.setdefault("role", "assistant")
        return msg

    async def complete_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        from app.services.doubao_client import (
            chat_completion_messages_stream,
            is_configured,
        )

        if tools:
            msg = await self.complete(messages, tools)
            text = str(msg.get("content") or "")
            if text:
                yield text
            return
        if not is_configured():
            yield "模型未配置，请稍后重试。"
            return
        cfg = self._cfg()
        async for tok in chat_completion_messages_stream(
            messages=messages,
            max_tokens=int(cfg.get("max_tokens") or 700),
            feature=f"harness.{self.profile}",
        ):
            yield tok


async def _complete_with_retry(
    adapter: ModelAdapter,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    retries: int = 1,
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(retries + 1):
        try:
            last = await adapter.complete(messages, tools)
        except Exception as e:
            logger.warning("llm complete failed attempt=%s err=%s", attempt, e)
            last = None
        if isinstance(last, dict) and (last.get("content") or last.get("tool_calls")):
            last.setdefault("role", "assistant")
            return last
        if attempt < retries:
            continue
    return last or {"role": "assistant", "content": "暂时无法生成回复。"}


async def run_agent(
    *,
    profile: str,
    user_message: str,
    thread_id: str | None = None,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    model: ModelAdapter | None = None,
    max_steps: int = 6,
    resume_tokens: list[str] | None = None,
    system_extra: str | None = None,
    system_override: str | None = None,
    fresh: bool = False,
    allow_tools: bool = True,
) -> AgentState:
    """跑一轮或从审批中断恢复。业务 facade 请用 run_profile_turn(fresh)。"""
    state: AgentState | None = None
    async for kind, payload in iter_agent(
        profile=profile,
        user_message=user_message,
        thread_id=thread_id,
        history=history,
        ctx=ctx,
        model=model,
        max_steps=max_steps,
        resume_tokens=resume_tokens,
        system_extra=system_extra,
        system_override=system_override,
        fresh=fresh,
        allow_tools=allow_tools,
    ):
        if kind == "done":
            state = payload
    assert state is not None
    return state


async def iter_agent(
    *,
    profile: str,
    user_message: str,
    thread_id: str | None = None,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    model: ModelAdapter | None = None,
    max_steps: int = 6,
    resume_tokens: list[str] | None = None,
    system_extra: str | None = None,
    system_override: str | None = None,
    fresh: bool = False,
    allow_tools: bool = True,
) -> AsyncIterator[tuple[str, Any]]:
    tid = (thread_id or uuid.uuid4().hex)[:32]
    state = None if fresh else load_state(tid)
    if user_message:
        gate = check_user_message(user_message)
        if not gate.allowed:
            failed = AgentState(
                thread_id=tid,
                profile=profile,
                status="failed",
                reply="问题过长，请缩短后再问。",
                metadata={"policy": gate.reason},
            )
            audit_loop("deny_message", thread_id=tid, profile=profile, extra={"reason": gate.reason})
            save_state(failed)
            yield ("done", failed)
            return
    if state is None:
        sys_msg = (system_override or "").strip() or profile_system(profile)
        extra = (system_extra or "").strip()
        if extra:
            sys_msg = f"{sys_msg}\n\n{extra}"
        msgs: list[dict[str, Any]] = [{"role": "system", "content": sys_msg}]
        for item in history or []:
            role = str(item.get("role") or "")
            if role not in ("user", "assistant", "tool"):
                continue
            msgs.append(item)
        if user_message:
            msgs.append({"role": "user", "content": user_message})
        state = AgentState(
            thread_id=tid,
            profile=profile,
            messages=msgs,
            max_steps=max_steps,
            metadata={"child_user_id": getattr(ctx, "child_user_id", 0) if ctx else 0},
        )
    elif user_message and state.status != "awaiting_approval":
        state.messages.append({"role": "user", "content": user_message})
        state.status = "running"
        state.reply = ""

    if resume_tokens and state.status == "awaiting_approval":
        state = await _resume_approvals(state, resume_tokens, ctx=ctx)

    for hook in _GATES.get(profile, []):
        extra_state = hook(state)
        if extra_state is not None and hasattr(extra_state, "__await__"):
            extra_state = await extra_state  # type: ignore[misc]
        if isinstance(extra_state, AgentState):
            state = extra_state
            if state.status in ("completed", "failed", "awaiting_approval"):
                save_state(state)
                yield ("done", state)
                return

    adapter = model or DeepSeekAdapter(profile)
    tools = openai_tools_for_profile(profile) if allow_tools else []
    streamer = getattr(adapter, "complete_stream", None)

    while state.status == "running" and state.step < state.max_steps:
        state.step += 1
        window, mem = window_for_model(state.messages, state.metadata.get("memory"))
        state.metadata["memory"] = mem
        t0 = time.perf_counter()
        live = bool(callable(streamer) and not tools)
        assistant: dict[str, Any]
        if live:
            chunks: list[str] = []
            async for piece in streamer(window, []):
                text = str(piece or "")
                if not text:
                    continue
                chunks.append(text)
                yield ("token", text)
            assistant = {"role": "assistant", "content": "".join(chunks)}
        else:
            assistant = await _complete_with_retry(adapter, window, tools)
        ms = int((time.perf_counter() - t0) * 1000)
        ok = bool(assistant.get("content") or assistant.get("tool_calls"))
        emit_trace("llm.complete", ms, ok, profile=profile)
        state.metadata["llm_calls"] = int(state.metadata.get("llm_calls") or 0) + 1
        state.messages.append(assistant)
        calls = parse_tool_calls(assistant) if tools else []
        if not calls:
            state.reply = str(assistant.get("content") or "").strip()
            state.status = "completed"
            if not live and state.reply:
                yield ("token", state.reply)
            break
        executed, paused = await _handle_calls(state, calls, ctx=ctx)
        if paused:
            state.status = "awaiting_approval"
            break
        if not executed:
            state.reply = str(assistant.get("content") or "").strip() or "工具调用未执行。"
            state.status = "completed"
            if state.reply:
                yield ("token", state.reply)
            break

    if state.status == "running":
        state.status = "completed"
        if not state.reply:
            state.reply = "本轮步数已用完，请根据已查到的信息继续提问。"
            yield ("token", state.reply)

    audit_loop(
        "complete",
        thread_id=state.thread_id,
        profile=profile,
        extra={"steps": state.step, "llm_calls": state.metadata.get("llm_calls") or 0},
    )
    save_state(state)
    yield ("done", state)


async def _handle_calls(
    state: AgentState,
    calls: list[dict[str, Any]],
    *,
    ctx: ToolContext | None,
) -> tuple[bool, bool]:
    executed = False
    paused = False
    for call in calls:
        name = call["name"]
        args = dict(call.get("args") or {})
        spec = get_tool(name)
        decision = check_tool(spec, name, profile=state.profile)
        if not decision.allowed:
            _append_tool(state, call["id"], name, {"ok": False, "error": decision.reason})
            executed = True
            continue
        if spec and spec.permission == "confirm":
            from app.harness import approval

            token = approval.issue(name, args, profile=state.profile)
            state.pending_approvals.append(
                PendingApproval(
                    tool=name,
                    arguments=args,
                    call_id=str(call["id"]),
                    confirm_token=token,
                )
            )
            _append_tool(
                state,
                call["id"],
                name,
                {"ok": False, "error": "needs_confirm", "confirm_token": token},
            )
            paused = True
            continue
        result = await call_tool(name, args, profile=state.profile, ctx=ctx)
        state.tool_trace.append(result.to_audit())
        _append_tool(state, call["id"], name, result.data | ({"error": result.error} if result.error else {}))
        executed = True
    return executed, paused


async def _resume_approvals(
    state: AgentState,
    tokens: list[str],
    *,
    ctx: ToolContext | None,
) -> AgentState:
    token_set = {t for t in tokens if t}
    still: list[PendingApproval] = []
    for pend in state.pending_approvals:
        if pend.confirm_token not in token_set:
            still.append(pend)
            continue
        result = await call_tool(
            pend.tool,
            {**pend.arguments, "confirm_token": pend.confirm_token},
            profile=state.profile,
            ctx=ctx,
        )
        state.tool_trace.append(result.to_audit())
        payload = result.data | ({"error": result.error} if result.error else {})
        state.messages.append(
            {
                "role": "user",
                "content": f"已批准工具 {pend.tool}，结果："
                + json.dumps(payload, ensure_ascii=False)[:1500],
            }
        )
    state.pending_approvals = still
    state.status = "running" if not still else "awaiting_approval"
    return state


def _append_tool(state: AgentState, call_id: str, name: str, payload: dict[str, Any]) -> None:
    state.messages.append(
        {
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": json.dumps(payload, ensure_ascii=False)[:4000],
        }
    )


def allowed_tool_names(profile: str) -> list[str]:
    return [t.name for t in aggregated_tools(profile=profile)]
