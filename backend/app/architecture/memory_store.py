"""状态怎么存 — 契约。

- RunCheckpointStore：单次 run 可恢复（PENDING/RUNNING/DONE）
- DurableMemoryStore：跨轮会话消息（guide/qa/report…）
"""

from __future__ import annotations

from typing import Any, Protocol


class RunCheckpointStore(Protocol):
    def save(self, thread_id: str, state: Any) -> None: ...

    def load(self, thread_id: str) -> Any | None: ...

    def clear(self, thread_id: str) -> None: ...


class DurableMemoryStore(Protocol):
    """持久会话；实现见 app.memory.ThreadStore。"""

    def list_messages(self, ref: Any, *, limit: int = 100) -> list[Any]: ...

    def append(
        self,
        ref: Any,
        *,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Any: ...

    def clear(self, ref: Any, *, commit: bool = True) -> int: ...
