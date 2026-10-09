"""统一编排循环 — 主流 Agent：model → tool_calls → execute/interrupt → 再 model。

形态对齐：
- OpenAI Agents SDK Runner：直到无 tool_calls 或 hit max_turns
- LangGraph ToolNode + interrupt：confirm 工具暂停，resume 后续跑
- Anthropic tool_use 环：assistant + tool 结果写回 messages

不做跨 Guide/QA/学院的超级编排；产品闸门通过 GateHook 挂在循环前。
"""

from __future__ import annotations

import asyncio
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

# allow_tools 时必须走 complete（才能拿 tool_calls），最终正文会整段返回；
# 切成小块再 SSE，避免学科答疑等场景「整段弹出」。
_STREAM_CHUNK_CHARS = 28
_STREAM_CHUNK_PAUSE_S = 0.01


async def _iter_text_tokens(text: str) -> AsyncIterator[str]:
    """把完整回复切成渐进 token，供非 live 路径模拟流式。"""
    s = str(text or "")
    if not s:
        return
    if len(s) <= _STREAM_CHUNK_CHARS:
        yield s
        return
    i = 0
    n = len(s)
    while i < n:
        j = min(i + _STREAM_CHUNK_CHARS, n)
        if j < n:
            # 向后多看一点，尽量在换行/标点处切断
            for k in range(j, min(n, j + 16)):
                if s[k] in "\n。！？；，、,.!?;: ":
                    j = k + 1
                    break
        piece = s[i:j]
        i = j
        if piece:
            yield piece
            await asyncio.sleep(_STREAM_CHUNK_PAUSE_S)


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
    try:
        from app.harness import gates as _gates_mod

        _gates_mod._INSTALLED = False
    except Exception:
        pass


class DeepSeekAdapter:
    """模型适配 → 委托 llm.route(profile)；流式仅透传。"""

    def __init__(self, profile: str = "harness") -> None:
        self.profile = profile

    def _route(self):
        from app.harness.llm import route

        return route(self.profile)

    def _cfg(self) -> dict[str, Any]:
        return self._route().cfg

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return await self._route().complete(messages, tools or None)

    async def complete_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        async for tok in self._route().stream(messages, tools or None):
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
    metadata: dict[str, Any] | None = None,
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
        metadata=metadata,
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
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    from app.harness.gates import install_builtin_gates

    install_builtin_gates()
    tid = (thread_id or uuid.uuid4().hex)[:32]
    state = None if fresh else load_state(tid)
    # 产品闸门短接：允许空 user_message（错科 / 引导话术已由门面写好 reply）
    has_product_gate = bool(
        isinstance((metadata or {}).get("product_gate"), dict)
        and str((metadata or {}).get("product_gate", {}).get("reply") or "").strip()
    )
    if user_message:
        gate = check_user_message(user_message, profile=profile)
        if not gate.allowed:
            from app.harness.safety import injection_refusal

            if gate.reason == "prompt_injection":
                deny_reply = injection_refusal(profile)
            else:
                deny_reply = "问题过长，请缩短后再问。"
            failed = AgentState(
                thread_id=tid,
                profile=profile,
                status="failed",
                reply=deny_reply,
                metadata={"policy": gate.reason},
            )
            audit_loop("deny_message", thread_id=tid, profile=profile, extra={"reason": gate.reason})
            save_state(failed)
            if deny_reply:
                yield ("token", deny_reply)
            yield ("done", failed)
            return
    if state is None:
        from app.harness.safety import anti_leak_rules_for_profile

        sys_msg = (system_override or "").strip() or profile_system(profile)
        extra = (system_extra or "").strip()
        if extra:
            sys_msg = f"{sys_msg}\n\n{extra}"
        leak = anti_leak_rules_for_profile(profile)
        if leak and leak not in sys_msg:
            sys_msg = f"{sys_msg}\n\n{leak}"
        msgs: list[dict[str, Any]] = [{"role": "system", "content": sys_msg}]
        for item in history or []:
            role = str(item.get("role") or "")
            if role not in ("user", "assistant", "tool"):
                continue
            msgs.append(item)
        if user_message:
            msgs.append({"role": "user", "content": user_message})
        elif has_product_gate:
            msgs.append({"role": "user", "content": ""})
        base_meta: dict[str, Any] = {
            "child_user_id": getattr(ctx, "child_user_id", 0) if ctx else 0,
        }
        if metadata:
            base_meta.update(metadata)
        state = AgentState(
            thread_id=tid,
            profile=profile,
            messages=msgs,
            max_steps=max_steps,
            metadata=base_meta,
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
                # 产品闸门短接也要吐 token，否则 SSE 前端只收到 done、气泡空白
                if state.status == "completed" and (state.reply or "").strip():
                    yield ("token", state.reply)
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
            # live 路径已在 streamer 里逐 token yield；complete 路径需补推
            if not live and state.reply:
                async for piece in _iter_text_tokens(state.reply):
                    yield ("token", piece)
            break
        executed, paused = await _handle_calls(state, calls, ctx=ctx)
        if paused:
            state.status = "awaiting_approval"
            break
        if not executed:
            state.reply = str(assistant.get("content") or "").strip() or "工具调用未执行。"
            state.status = "completed"
            if state.reply:
                async for piece in _iter_text_tokens(state.reply):
                    yield ("token", piece)
            break

    if state.status == "running":
        state.status = "completed"
        if not state.reply:
            state.reply = "本轮步数已用完，请根据已查到的信息继续提问。"
            async for piece in _iter_text_tokens(state.reply):
                yield ("token", piece)

    if state.status == "completed":
        appended = _append_math_sketch_fence(state)
        if appended and state.reply:
            yield ("token", "\n\n" + appended)
        # 对外回复再过一遍：去 Thought 草稿 + 防泄露（学院/答疑共用）
        from app.harness.safety import sanitize_public_reply

        cleaned = sanitize_public_reply(state.reply or "", profile=profile)
        if cleaned != (state.reply or ""):
            state.reply = cleaned

    audit_loop(
        "complete",
        thread_id=state.thread_id,
        profile=profile,
        extra={"steps": state.step, "llm_calls": state.metadata.get("llm_calls") or 0},
    )
    save_state(state)
    yield ("done", state)


def _append_math_sketch_fence(state: AgentState) -> str:
    """若 math_sketch 已产出 fence 但最终回复未粘贴，补上以免前端丢图。"""
    reply = (state.reply or "").strip()
    if "jnao-svg" in reply:
        return ""
    for msg in reversed(state.messages or []):
        if msg.get("role") != "tool":
            continue
        if str(msg.get("name") or "") != "math_sketch":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or not payload.get("ok"):
            continue
        fence = str(payload.get("fence") or "").strip()
        if not fence or "jnao-svg" not in fence:
            continue
        state.reply = f"{reply}\n\n{fence}".strip() if reply else fence
        return fence
    return ""


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
