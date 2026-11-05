"""费用怎么记 — 契约（Fee 横切）。

Agent / Harness / 工具只依赖本 Protocol，不直接碰 usage 表或费率实现。
实现落在 app.model_cost（UsageLedger）。
"""

from __future__ import annotations

from typing import Any, Protocol


class CostMeter(Protocol):
    """一次上游调用的计量入口；汇总按 AgentFeature。"""

    def record(self, event: Any) -> None:
        """写入计量事件（token / 估算 RAG 等）。"""
        ...

    def bind_feature(self, feature: str) -> None:
        """绑定当前请求上下文的 Agent 板块（feature）。"""
        ...

    def summarize(
        self,
        *,
        user_id: int | None = None,
        billing_parent_id: int | None = None,
    ) -> list[Any]:
        """按 feature 聚合用量与已落库成本快照。"""
        ...
