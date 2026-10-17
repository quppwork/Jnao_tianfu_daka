"""Tool call protocol."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    id: str
    name: str
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None

    def to_audit(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }
