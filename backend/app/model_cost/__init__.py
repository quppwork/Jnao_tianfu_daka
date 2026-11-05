"""Fee 横切 — Agent 架构「费用」角色（非 Agent / 非 Harness 内核）。

业务只依赖 CostRecorder / AgentFeature；落库 UsageLedger → usage_recorder。
分层说明见 ARCHITECTURE.md；契约见 architecture.CostMeter。
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
