"""Chat message protocol."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def to_openai(self) -> dict[str, Any]:
        row: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            row["name"] = self.name
        if self.tool_call_id:
            row["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            row["tool_calls"] = self.tool_calls
        return row

    @classmethod
    def from_openai(cls, raw: dict[str, Any]) -> ChatMessage:
        return cls(
            role=str(raw.get("role") or "user"),  # type: ignore[arg-type]
            content=str(raw.get("content") or ""),
            name=raw.get("name"),
            tool_call_id=raw.get("tool_call_id"),
            tool_calls=raw.get("tool_calls"),
        )
