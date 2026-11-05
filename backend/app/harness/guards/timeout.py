"""保障：防卡死 — 单次 turn / 工具超时预算（秒）。"""

from __future__ import annotations

import time
from typing import Any

from app.architecture.guard_policy import GuardDecision


class TimeoutGuard:
    name = "timeout"

    def __init__(
        self,
        *,
        turn_timeout_s: float = 120.0,
        tool_timeout_s: float = 60.0,
    ) -> None:
        self.turn_timeout_s = float(turn_timeout_s)
        self.tool_timeout_s = float(tool_timeout_s)

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        del profile
        metadata["_turn_deadline"] = time.monotonic() + self.turn_timeout_s
        return GuardDecision(True)

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del profile, tool, arguments
        deadline = float(metadata.get("_turn_deadline") or 0)
        if deadline and time.monotonic() > deadline:
            return GuardDecision(False, "turn timeout", "timeout")
        metadata["_tool_deadline"] = time.monotonic() + self.tool_timeout_s
        return GuardDecision(True)

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del profile, step, max_steps
        deadline = float(metadata.get("_turn_deadline") or 0)
        if deadline and time.monotonic() > deadline:
            return GuardDecision(False, "turn timeout", "timeout")
        return GuardDecision(True)

    def remaining_tool_s(self, metadata: dict[str, Any]) -> float | None:
        deadline = metadata.get("_tool_deadline")
        if not deadline:
            return self.tool_timeout_s
        return max(0.0, float(deadline) - time.monotonic())
