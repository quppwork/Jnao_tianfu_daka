"""while 循环门面 — 无脑执行；保障经 GuardPolicy，模型/工具经 Provider。

底层循环仍委托 harness.loop（实现细节）；业务只调本模块。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.architecture.guard_policy import GuardDecision
from app.harness.agent_state import AgentState
from app.harness.context import ToolContext
from app.harness.guards.composite import CompositeGuard
from app.runtime.public import public_turn


class Executor:
    """组装后的编排器：guards → loop → providers。"""

    def __init__(
        self,
        *,
        guards: CompositeGuard,
        llm: Any | None = None,
        mcp: Any | None = None,
        checkpoint: Any | None = None,
    ) -> None:
        self.guards = guards
        self.llm = llm
        self.mcp = mcp
        self.checkpoint = checkpoint

    def _deny_state(
        self,
        *,
        profile: str,
        thread_id: str,
        decision: GuardDecision,
        reply: str,
    ) -> AgentState:
        return AgentState(
            thread_id=thread_id[:32],
            profile=profile,
            status="failed",
            reply=reply,
            metadata={"guard": decision.code or decision.reason},
        )

    async def run(
        self,
        profile: str,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        ctx: ToolContext | None = None,
        system_extra: str = "",
        system_override: str | None = None,
        max_steps: int = 6,
        max_tool_rounds: int | None = None,
        thread_id: str | None = None,
        model: Any | None = None,
        allow_tools: bool = True,
        metadata: dict[str, Any] | None = None,
        fresh: bool = True,
    ) -> dict[str, Any]:
        import uuid

        from app.harness.loop import run_agent

        meta = dict(metadata or {})
        tid = (thread_id or uuid.uuid4().hex)[:32]
        meta.setdefault("thread_id", tid)

        # 输入权限
        perms = self.guards.permissions()
        if user_message and perms is not None:
            d = perms.check_user_message(user_message, profile=profile)
            if not d.allowed:
                from app.harness.safety import injection_refusal

                reply = (
                    injection_refusal(profile)
                    if d.reason == "prompt_injection"
                    else "问题过长，请缩短后再问。"
                )
                state = self._deny_state(
                    profile=profile, thread_id=tid, decision=d, reply=reply
                )
                return public_turn(state, profile)

        d = self.guards.before_turn(profile=profile, metadata=meta)
        if not d.allowed:
            state = self._deny_state(
                profile=profile,
                thread_id=tid,
                decision=d,
                reply="当前服务暂时不可用，请稍后再试。",
            )
            return public_turn(state, profile)

        try:
            state = await run_agent(
                profile=profile,
                user_message=user_message,
                thread_id=tid,
                history=history,
                ctx=ctx,
                model=model,
                max_steps=max_steps,
                max_tool_rounds=max_tool_rounds,
                system_extra=system_extra or None,
                system_override=system_override,
                fresh=fresh,
                allow_tools=allow_tools,
                metadata=meta,
            )
        except Exception:
            circuit = self.guards.circuit()
            if circuit:
                circuit.record_failure(profile)
            raise

        circuit = self.guards.circuit()
        if circuit:
            if state.status == "failed":
                circuit.record_failure(profile)
            else:
                circuit.record_success(profile)

        self.guards.after_step(
            profile=profile,
            step=int(state.step or 0),
            max_steps=int(state.max_steps or max_steps),
            metadata=state.metadata or meta,
        )
        return public_turn(state, profile)

    async def stream(
        self,
        profile: str,
        user_message: str,
        *,
        history: list[dict[str, Any]] | None = None,
        ctx: ToolContext | None = None,
        system_extra: str = "",
        system_override: str | None = None,
        max_steps: int = 6,
        max_tool_rounds: int | None = None,
        thread_id: str | None = None,
        model: Any | None = None,
        allow_tools: bool = False,
        metadata: dict[str, Any] | None = None,
        fresh: bool = True,
    ) -> AsyncIterator[tuple[str, Any]]:
        import uuid

        from app.harness.loop import iter_agent

        meta = dict(metadata or {})
        tid = (thread_id or uuid.uuid4().hex)[:32]
        meta.setdefault("thread_id", tid)

        perms = self.guards.permissions()
        if user_message and perms is not None:
            d = perms.check_user_message(user_message, profile=profile)
            if not d.allowed:
                from app.harness.safety import injection_refusal

                reply = (
                    injection_refusal(profile)
                    if d.reason == "prompt_injection"
                    else "问题过长，请缩短后再问。"
                )
                yield ("token", reply)
                yield (
                    "done",
                    public_turn(
                        self._deny_state(
                            profile=profile, thread_id=tid, decision=d, reply=reply
                        ),
                        profile,
                    ),
                )
                return

        d = self.guards.before_turn(profile=profile, metadata=meta)
        if not d.allowed:
            reply = "当前服务暂时不可用，请稍后再试。"
            yield ("token", reply)
            yield (
                "done",
                public_turn(
                    self._deny_state(
                        profile=profile, thread_id=tid, decision=d, reply=reply
                    ),
                    profile,
                ),
            )
            return

        async for kind, payload in iter_agent(
            profile=profile,
            user_message=user_message,
            thread_id=tid,
            history=history,
            ctx=ctx,
            model=model,
            max_steps=max_steps,
            max_tool_rounds=max_tool_rounds,
            system_extra=system_extra or None,
            system_override=system_override,
            fresh=fresh,
            allow_tools=allow_tools,
            metadata=meta,
        ):
            if kind == "token":
                text = str(payload or "")
                if text.startswith("[ERROR]"):
                    yield ("error", text)
                    return
                yield ("token", text)
            elif kind == "done":
                circuit = self.guards.circuit()
                if circuit:
                    if getattr(payload, "status", "") == "failed":
                        circuit.record_failure(profile)
                    else:
                        circuit.record_success(profile)
                yield ("done", public_turn(payload, profile))


def _executor() -> Executor:
    from app.assemble import get_bundle

    return get_bundle().executor


async def run_turn(
    profile: str,
    user_message: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """业务统一入口（取代直接调 harness.turn）。"""
    return await _executor().run(profile, user_message, **kwargs)


async def run_turn_stream(
    profile: str,
    user_message: str,
    **kwargs: Any,
) -> AsyncIterator[tuple[str, Any]]:
    async for item in _executor().stream(profile, user_message, **kwargs):
        yield item
