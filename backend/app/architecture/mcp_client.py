"""工具怎么调 — 契约（MCP / ToolBus）。"""

from __future__ import annotations

from typing import Any, Protocol


class McpClient(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any: ...
