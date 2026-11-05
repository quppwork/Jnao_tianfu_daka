"""保障：安全防线 — 拦截越权工具 / 注入（委托 policy）。"""

from __future__ import annotations

from typing import Any

from app.architecture.guard_policy import GuardDecision


class PermissionsGuard:
    name = "permissions"

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        del metadata
        # 用户消息校验在 runtime 入口对 user_message 调用；此处只占位
        del profile
        return GuardDecision(True)

    def check_user_message(self, text: str, *, profile: str | None = None) -> GuardDecision:
        from app.harness.policy import check_user_message

        d = check_user_message(text, profile=profile)
        return GuardDecision(d.allowed, d.reason, d.reason)

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del arguments, metadata
        from app.harness.policy import check_tool
        from app.harness.registry import get_tool

        spec = get_tool(tool)
        d = check_tool(spec, tool, profile=profile)
        return GuardDecision(d.allowed, d.reason, d.reason)

    def after_step(
        self,
        *,
        profile: str,
        step: int,
        max_steps: int,
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del profile, step, max_steps, metadata
        return GuardDecision(True)
