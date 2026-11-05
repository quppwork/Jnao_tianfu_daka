"""保障：钱不能烧光 — 高成本调用预检（接 model_cost）。"""

from __future__ import annotations

from typing import Any

from app.architecture.guard_policy import GuardDecision


# 当前 LLM 对话默认不硬挡；工具名命中高成本集合时记入 metadata，供后续钱包闸启用。
HIGH_COST_TOOLS = frozenset({
    "gen_image",
    "gen_video",
    "canvas_run_node",
    "canvas_run_subgraph",
})


class BudgetGuard:
    name = "budget"

    def __init__(self, *, enforce: bool = False) -> None:
        self.enforce = enforce

    def before_turn(self, *, profile: str, metadata: dict[str, Any]) -> GuardDecision:
        del profile
        if metadata.get("budget_exhausted"):
            return GuardDecision(False, "budget exhausted", "budget")
        return GuardDecision(True)

    def before_tool(
        self,
        *,
        profile: str,
        tool: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
    ) -> GuardDecision:
        del profile, arguments
        if tool not in HIGH_COST_TOOLS:
            return GuardDecision(True)
        metadata.setdefault("high_cost_tools", [])
        if isinstance(metadata["high_cost_tools"], list):
            metadata["high_cost_tools"].append(tool)
        if self.enforce and metadata.get("budget_exhausted"):
            return GuardDecision(False, f"budget blocks {tool}", "budget")
        # 绑定费用 feature，供 ledger 归因
        try:
            from app.model_cost import get_cost_recorder

            feature = metadata.get("feature")
            if feature:
                get_cost_recorder().bind_feature(str(feature))
        except Exception:
            pass
        return GuardDecision(True)

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
