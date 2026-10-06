"""统一 Agent 状态 — 对齐 LangGraph / OpenAI Agents SDK 的 thread state。

messages 用 OpenAI 角色：system / user / assistant / tool。
审批中断时 status=awaiting_approval，检查点按 thread_id 保存，resume 后继续。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AgentStatus = Literal["running", "awaiting_approval", "completed", "failed"]


@dataclass
class PendingApproval:
    tool: str
    arguments: dict[str, Any]
    call_id: str
    confirm_token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "call_id": self.call_id,
            "confirm_token": self.confirm_token,
        }


@dataclass
class AgentState:
    thread_id: str
    profile: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    status: AgentStatus = "running"
    step: int = 0
    max_steps: int = 6
    reply: str = ""
    pending_approvals: list[PendingApproval] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "profile": self.profile,
            "status": self.status,
            "step": self.step,
            "reply": self.reply,
            "pending_approvals": [p.to_dict() for p in self.pending_approvals],
            "tool_trace": self.tool_trace[-12:],
        }
