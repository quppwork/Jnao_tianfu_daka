"""模型费用组件 — 各 Agent 板块计费入口，与业务编排解耦。

业务只依赖 CostRecorder / Feature 常量；落库走 UsageLedger → usage_recorder。
"""

from app.model_cost.features import AgentFeature, feature_label
from app.model_cost.ledger import UsageLedger, get_cost_recorder
from app.model_cost.protocols import CostEvent, CostRecorder, CostSummary
from app.model_cost.rates import ModelRate, RateCard, default_rate_card

__all__ = [
    "AgentFeature",
    "CostEvent",
    "CostRecorder",
    "CostSummary",
    "ModelRate",
    "RateCard",
    "UsageLedger",
    "default_rate_card",
    "feature_label",
    "get_cost_recorder",
]
