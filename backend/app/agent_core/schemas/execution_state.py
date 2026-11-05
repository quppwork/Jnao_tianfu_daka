"""Execution status and RunState."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    DONE = "done"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"

    def to_agent_status(self) -> str:
        if self in (ExecutionStatus.DONE, ExecutionStatus.COMPLETED):
            return "completed"
        if self == ExecutionStatus.ABORTED:
            return "failed"
        if self == ExecutionStatus.PENDING:
            return "running"
        return self.value


class RunState(BaseModel):
    thread_id: str
    profile: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    step: int = 0
    max_steps: int = 6
    reply: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_agent_state(cls, state: Any) -> RunState:
        status_raw = str(getattr(state, "status", "running") or "running")
        try:
            status = ExecutionStatus(status_raw)
        except ValueError:
            status = (
                ExecutionStatus.COMPLETED
                if status_raw == "completed"
                else ExecutionStatus.RUNNING
            )
        pending = getattr(state, "pending_approvals", None) or []
        pending_dicts = [
            p.to_dict() if hasattr(p, "to_dict") else dict(p) for p in pending
        ]
        return cls(
            thread_id=str(state.thread_id),
            profile=str(state.profile),
            status=status,
            step=int(getattr(state, "step", 0) or 0),
            max_steps=int(getattr(state, "max_steps", 6) or 6),
            reply=str(getattr(state, "reply", "") or ""),
            messages=list(getattr(state, "messages", None) or []),
            tool_trace=list(getattr(state, "tool_trace", None) or []),
            pending_approvals=pending_dicts,
            metadata=dict(getattr(state, "metadata", None) or {}),
        )
