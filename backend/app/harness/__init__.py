"""执行保障 + 工具 / MCP / 沙箱。

业务出话请走 app.runtime.run_turn；本包保留 loop / tools / 兼容 turn shim。
架构见 app.agents.ARCHITECTURE.md 与 app.assemble。
"""

from app.harness.client import GatewayMCPClient
from app.harness.evidence import create_evidence, get_ledger
from app.harness.llm import PROFILES, complete, complete_stream, profile_system, route
from app.harness.loop import iter_agent, run_agent
from app.harness.memory import fold_and_truncate, fold_overflow_history, truncate_history, window_for_model
from app.harness.orchestration import ORCHESTRATION_MODE, handoff_packet
from app.harness.runtime import call_tool, harness_status
from app.harness.trace import emit as trace
# 兼容旧名；规范入口是 app.runtime.run_turn
from app.runtime import run_turn as run_profile_turn
from app.runtime import run_turn_stream as run_profile_turn_stream

__all__ = [
    "ORCHESTRATION_MODE",
    "PROFILES",
    "GatewayMCPClient",
    "call_tool",
    "complete",
    "complete_stream",
    "create_evidence",
    "fold_and_truncate",
    "fold_overflow_history",
    "get_ledger",
    "handoff_packet",
    "harness_status",
    "iter_agent",
    "profile_system",
    "route",
    "run_agent",
    "run_profile_turn",
    "run_profile_turn_stream",
    "trace",
    "truncate_history",
    "window_for_model",
]
