"""检查点 — LangGraph InMemorySaver 同款语义：按 thread_id 存整份 AgentState。

MySQL checkpointer 已在学院 runtime 使用；Harness 默认内存，测试隔离。
"""

from __future__ import annotations

import copy
from typing import Any

from app.harness.agent_state import AgentState, PendingApproval

_THREADS: dict[str, AgentState] = {}


def save_state(state: AgentState) -> None:
    _THREADS[state.thread_id] = copy.deepcopy(state)


def load_state(thread_id: str) -> AgentState | None:
    row = _THREADS.get(thread_id)
    return copy.deepcopy(row) if row else None


def clear_thread(thread_id: str) -> None:
    _THREADS.pop(thread_id, None)


def reset_all() -> None:
    _THREADS.clear()


def from_public_approval(raw: dict[str, Any]) -> PendingApproval:
    return PendingApproval(
        tool=str(raw.get("tool") or ""),
        arguments=dict(raw.get("arguments") or {}),
        call_id=str(raw.get("call_id") or ""),
        confirm_token=str(raw.get("confirm_token") or ""),
    )
