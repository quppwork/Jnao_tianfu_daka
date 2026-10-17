"""保障机制怎么拦 — Harness 契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str = ""
    code: str = ""


class GuardPolicy(Protocol):
    """单次 run 前后的保障钩子。任一拦下则短路。"""

    name: str

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        """进入循环前。"""
        ...

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        """执行工具前。"""
        ...

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        """每步结束后（熔断 / 步数）。"""
        ...
