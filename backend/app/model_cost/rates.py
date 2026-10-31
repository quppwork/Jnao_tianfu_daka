"""费率表 — 估算用，与真实充值点解耦；可按 provider/model 覆盖。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRate:
    """单价：每 1K token 的 milli-cent（0.001 分），仅用于展示估算。"""

    provider: str
    model: str
    prompt_per_1k_milli: int
    completion_per_1k_milli: int

    def estimate_milli(
        self, *, prompt_tokens: int, completion_tokens: int
    ) -> int:
        p = max(0, int(prompt_tokens))
        c = max(0, int(completion_tokens))
        return (p * self.prompt_per_1k_milli + c * self.completion_per_1k_milli) // 1000


@dataclass
class RateCard:
    rates: list[ModelRate]
    default: ModelRate

    def resolve(self, provider: str, model: str | None = None) -> ModelRate:
        prov = (provider or "").strip().lower()
        mod = (model or "").strip().lower()
        for row in self.rates:
            if row.provider == prov and (not mod or row.model == mod or row.model == "*"):
                return row
        for row in self.rates:
            if row.provider == prov and row.model == "*":
                return row
        return self.default


def default_rate_card() -> RateCard:
    """占位费率：便于看板估算，不替代 credit 扣点规则。"""
    return RateCard(
        rates=[
            ModelRate("doubao", "*", 2, 6),
            ModelRate("bailian", "*", 1, 1),
            ModelRate("dashscope", "*", 1, 3),
        ],
        default=ModelRate("*", "*", 2, 6),
    )
