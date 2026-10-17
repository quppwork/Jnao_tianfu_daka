"""Agent events: token / tool_progress / status / error / done / trace."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventKind(str, Enum):
    TOKEN = "token"
    TOOL_PROGRESS = "tool_progress"
    STATUS = "status"
    ERROR = "error"
    DONE = "done"
    TRACE = "trace"


class AgentEvent(BaseModel):
    kind: EventKind
    payload: Any = None
    profile: str | None = None
    thread_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def as_tuple(self) -> tuple[str, Any]:
        return (self.kind.value, self.payload)
