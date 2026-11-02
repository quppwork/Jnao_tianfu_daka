"""契约层 — 纯 Protocol，定义插件规范（无 I/O 实现）。

对照：llm-provider / mcp-client / memory-store / guard-policy / cost-meter。
"""

from app.architecture.cost_meter import CostMeter
from app.architecture.guard_policy import GuardDecision, GuardPolicy
from app.architecture.llm_provider import LlmCompletion, LlmProvider
from app.architecture.mcp_client import McpClient
from app.architecture.memory_store import DurableMemoryStore, RunCheckpointStore

__all__ = [
    "CostMeter",
    "DurableMemoryStore",
    "GuardDecision",
    "GuardPolicy",
    "LlmCompletion",
    "LlmProvider",
    "McpClient",
    "RunCheckpointStore",
]
