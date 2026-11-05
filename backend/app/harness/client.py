"""宿主侧 MCP 客户端。list/call 走聚合网关，业务代码不感知工具在沙箱内还是沙箱外。"""

from __future__ import annotations

from typing import Any

from app.harness.catalog import aggregated_tools, mcp_tool_list
from app.harness.policy import check_tool
from app.harness.types import ToolResult


class GatewayMCPClient:
    def __init__(self, *, profile: str | None = None, sandbox_id: str | None = None) -> None:
        self.profile = profile
        self.sandbox_id = sandbox_id

    def list_tools(self) -> list[dict[str, Any]]:
        return mcp_tool_list(profile=self.profile)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        from app.harness.registry import get_tool
        from app.harness.runtime import call_tool

        spec = get_tool(name)
        decision = check_tool(spec, name, profile=self.profile)
        if not decision.allowed:
            return ToolResult(ok=False, name=name, error=decision.reason)
        return await call_tool(name, arguments, profile=self.profile)

    def describe(self) -> dict[str, Any]:
        tools = aggregated_tools(profile=self.profile)
        return {
            "profile": self.profile,
            "sandbox_id": self.sandbox_id,
            "host_tools": [t.name for t in tools if t.plane == "host"],
            "sandbox_tools": [t.name for t in tools if t.plane == "sandbox"],
        }
