from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

Isolation = Literal["none", "process"]
Permission = Literal["readonly", "confirm"]
ToolPlane = Literal["host", "sandbox"]

ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    isolation: Isolation = "none"
    permission: Permission = "readonly"
    profiles: tuple[str, ...] = ()
    plane: ToolPlane = "host"
    mcp_server: str = "jnao-host"
    needs_db: bool = False


@dataclass
class ToolResult:
    ok: bool
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    isolation: str = "none"
    duration_ms: int = 0
    evidence_id: str | None = None
    content_sha256: str | None = None

    def to_audit(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "error": self.error,
            "isolation": self.isolation,
            "duration_ms": self.duration_ms,
            "evidence_id": self.evidence_id,
            "content_sha256": self.content_sha256,
        }

    def to_mcp_content(self) -> dict[str, Any]:
        import json

        payload = dict(self.data)
        if self.error:
            payload["error"] = self.error
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "isError": not self.ok,
        }
