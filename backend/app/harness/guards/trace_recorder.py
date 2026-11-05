"""Trace recorder guard — delegates to harness.trace / audit."""

from __future__ import annotations

from typing import Any

from app.architecture.guard_policy import GuardDecision


class TraceRecorderGuard:
    name = "trace"

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        from app.harness.audit import audit_loop
        from app.harness.trace import emit as emit_trace

        emit_trace("turn.start", 0, True, profile=profile)
        audit_loop(
            "turn_start",
            thread_id=str(metadata.get("thread_id") or ""),
            profile=profile,
            extra={"feature": metadata.get("feature")},
        )
        return GuardDecision(True)

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del arguments, metadata
        from app.harness.trace import emit as emit_trace

        emit_trace(f"tool.before:{tool}", 0, True, profile=profile)
        return GuardDecision(True)

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        from app.harness.trace import emit as emit_trace

        emit_trace(
            f"turn.step:{step}/{max_steps}",
            0,
            True,
            profile=profile,
            error=None,
        )
        # keep llm_calls in metadata only; emit() has fixed signature
        del metadata
        return GuardDecision(True)
