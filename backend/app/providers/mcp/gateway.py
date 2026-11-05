"""MCP 客户端适配器 — 委托 GatewayMCPClient / runtime.call_tool。"""

from __future__ import annotations

from typing import Any


class GatewayMcpProvider:
    """实现 architecture.McpClient。"""

    def __init__(self, *, profile: str | None = None) -> None:
        self.profile = profile

    def list_tools(self) -> list[dict[str, Any]]:
        from app.harness.client import GatewayMCPClient

        return GatewayMCPClient(profile=self.profile).list_tools()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        from app.harness.client import GatewayMCPClient

        return await GatewayMCPClient(profile=self.profile).call_tool(name, arguments)
