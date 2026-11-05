"""组合保障 — 按顺序执行，任一 deny 即短路。"""

from __future__ import annotations

from typing import Any

from app.architecture.guard_policy import GuardDecision, GuardPolicy
from app.harness.guards.budget import BudgetGuard
from app.harness.guards.circuit_breaker import CircuitBreakerGuard
from app.harness.guards.permissions import PermissionsGuard
from app.harness.guards.timeout import TimeoutGuard
from app.harness.guards.trace_recorder import TraceRecorderGuard


class CompositeGuard:
    name = "composite"

    def __init__(self, guards: list[GuardPolicy] | None = None) -> None:
        self.guards: list[GuardPolicy] = list(guards or [])

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        for g in self.guards:
            d = g.before_turn(profile=profile, metadata=metadata)
            if not d.allowed:
                return d
        return GuardDecision(True)

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        for g in self.guards:
            d = g.before_tool(
                profile=profile, tool=tool, arguments=arguments, metadata=metadata
            )
            if not d.allowed:
                return d
        return GuardDecision(True)

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        for g in self.guards:
            d = g.after_step(
                profile=profile, step=step, max_steps=max_steps, metadata=metadata
            )
            if not d.allowed:
                return d
        return GuardDecision(True)

    def permissions(self) -> PermissionsGuard | None:
        for g in self.guards:
            if isinstance(g, PermissionsGuard):
                return g
        return None

    def circuit(self) -> CircuitBreakerGuard | None:
        for g in self.guards:
            if isinstance(g, CircuitBreakerGuard):
                return g
        return None


def default_guards() -> CompositeGuard:
    return CompositeGuard(
        [
            TraceRecorderGuard(),
            TimeoutGuard(),
            BudgetGuard(enforce=False),
            CircuitBreakerGuard(),
            PermissionsGuard(),
        ]
    )
