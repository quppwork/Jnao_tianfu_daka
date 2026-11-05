"""外部 MCP 客户端协议 — 与官方 SDK 解耦，便于换实现。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ExternalToolDesc:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server: str = ""


@dataclass
class RemoteCallResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    raw: Any = None


class ExternalMCPClient(Protocol):
    """对接他人 MCP Server（或其官方 SDK 包装）时实现此协议。"""

    name: str

    async def list_tools(self) -> list[ExternalToolDesc]: ...

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> RemoteCallResult: ...
