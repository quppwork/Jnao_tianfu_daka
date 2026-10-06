"""薄 Harness：Tool / MCP / 沙箱 + 统一 run_agent。会话表仍分域。"""

from app.harness.client import GatewayMCPClient
from app.harness.llm import PROFILES, complete
from app.harness.loop import iter_agent, run_agent
from app.harness.memory import fold_and_truncate, fold_overflow_history, truncate_history, window_for_model
from app.harness.orchestration import ORCHESTRATION_MODE, handoff_packet
from app.harness.runtime import call_tool, harness_status
from app.harness.trace import emit as trace
from app.harness.turn import run_profile_turn, run_profile_turn_stream

__all__ = [
    "ORCHESTRATION_MODE",
    "PROFILES",
    "GatewayMCPClient",
    "call_tool",
    "complete",
    "fold_and_truncate",
    "fold_overflow_history",
    "handoff_packet",
    "harness_status",
    "iter_agent",
    "run_agent",
    "run_profile_turn",
    "run_profile_turn_stream",
    "trace",
    "truncate_history",
    "window_for_model",
]
