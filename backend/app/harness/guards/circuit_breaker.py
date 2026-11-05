"""保障：防死循环 / 防雪崩 — 步数熔断 + 连续失败熔断。"""

from __future__ import annotations

from typing import Any

from app.architecture.guard_policy import GuardDecision


class CircuitBreakerGuard:
    name = "circuit_breaker"

    def __init__(self, *, max_failures: int = 3) -> None:
        self.max_failures = max(1, int(max_failures))
        self._fail_streak: dict[str, int] = {}

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        del metadata
        if self._fail_streak.get(profile, 0) >= self.max_failures:
            return GuardDecision(
                False,
                f"circuit open for profile={profile}",
                "circuit_open",
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
        del profile, tool, arguments, metadata
        return GuardDecision(True)

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del metadata
        if step >= max_steps:
            return GuardDecision(False, "max_steps reached", "max_steps")
        return GuardDecision(True)

    def record_success(self, profile: str) -> None:
        self._fail_streak[profile] = 0

    def record_failure(self, profile: str) -> None:
        self._fail_streak[profile] = self._fail_streak.get(profile, 0) + 1
