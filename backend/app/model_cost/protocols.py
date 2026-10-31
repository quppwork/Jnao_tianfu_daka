"""计费抽象 — Agent 只依赖本协议，不直接碰 usage_recorder / 账本表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CostEvent:
    """一次上游模型或 RAG 调用的计量事件。"""

    provider: str
    feature: str
    api: str | None = None
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 1
    doc_count: int = 0
    metric_kind: str = "tokens"
    estimated: bool = False
    ok: bool = True
    user_id: int | None = None
    request_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CostSummary:
    feature: str
    label: str
    total_tokens: int
    call_count: int
    estimated_cost_milli: int
    by_provider: list[dict[str, Any]] = field(default_factory=list)


class CostRecorder(Protocol):
    def record(self, event: CostEvent) -> None: ...

    def bind_feature(self, feature: str) -> None: ...

    def summarize(
        self,
        *,
        user_id: int | None = None,
        billing_parent_id: int | None = None,
    ) -> list[CostSummary]: ...
