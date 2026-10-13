"""外部 MCP 适配器注册表。"""

from __future__ import annotations

from typing import Any

from app.harness.mcp_adapters.base import ExternalMCPClient, ExternalToolDesc, RemoteCallResult


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ExternalMCPClient] = {}

    def register(self, client: ExternalMCPClient) -> None:
        self._adapters[client.name] = client

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    def get(self, name: str) -> ExternalMCPClient | None:
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        return sorted(self._adapters.keys())

    async def list_all_tools(self) -> list[ExternalToolDesc]:
        out: list[ExternalToolDesc] = []
        for client in self._adapters.values():
            tools = await client.list_tools()
            for t in tools:
                out.append(
                    ExternalToolDesc(
                        name=t.name,
                        description=t.description,
                        input_schema=dict(t.input_schema or {}),
                        server=t.server or client.name,
                    )
                )
        return out

    async def call(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        server: str | None = None,
    ) -> RemoteCallResult:
        """按 server 指定，或在各 adapter 中按工具名查找。"""
        if server:
            client = self._adapters.get(server)
            if not client:
                return RemoteCallResult(ok=False, error=f"unknown mcp adapter: {server}")
            return await client.call_tool(tool, arguments)

        for client in self._adapters.values():
            tools = await client.list_tools()
            if any(t.name == tool for t in tools):
                return await client.call_tool(tool, arguments)
        return RemoteCallResult(ok=False, error=f"tool not found on any adapter: {tool}")

    def clear(self) -> None:
        self._adapters.clear()


_REGISTRY = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    return _REGISTRY


def register_adapter(client: ExternalMCPClient) -> None:
    _REGISTRY.register(client)
