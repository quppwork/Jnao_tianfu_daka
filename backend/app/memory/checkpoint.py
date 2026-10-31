"""快速恢复的当前 run 状态 — 委托 harness.checkpoint。"""

from __future__ import annotations

from typing import Any

from app.harness.checkpoint import clear_thread, load_state, reset_all, save_state


class CheckpointStore:
    """实现 architecture.RunCheckpointStore。"""

    def save(self, thread_id: str, state: Any) -> None:
        del thread_id  # AgentState 自带 thread_id
        save_state(state)

    def load(self, thread_id: str) -> Any | None:
        return load_state(thread_id)

    def clear(self, thread_id: str) -> None:
        clear_thread(thread_id)

    def reset_all(self) -> None:
        reset_all()
