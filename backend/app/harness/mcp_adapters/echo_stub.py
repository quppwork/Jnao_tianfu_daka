"""示例外部 MCP Adapter — 演示 register_adapter；生产可换成官方 SDK 包装。"""

from __future__ import annotations

from typing import Any

from app.harness.mcp_adapters.base import ExternalToolDesc, RemoteCallResult


class EchoStubMCP:
    """本地回声工具，用于联调适配层，不访问外网。"""

    name = "jnao-echo-stub"

    async def list_tools(self) -> list[ExternalToolDesc]:
        return [
            ExternalToolDesc(
                name="echo.ping",
                description="外部 MCP 适配示例：原样回显 text。",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
                server=self.name,
            )
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> RemoteCallResult:
        args = dict(arguments or {})
        if name != "echo.ping":
            return RemoteCallResult(ok=False, error=f"unknown tool {name}")
        return RemoteCallResult(ok=True, data={"echo": str(args.get("text") or "")})


def maybe_register_echo_stub() -> bool:
    """HARNESS_MCP_ECHO_STUB=1 时注册。"""
    import os

    if os.getenv("HARNESS_MCP_ECHO_STUB", "0").strip() not in ("1", "true", "True"):
        return False
    from app.harness.mcp_adapters import register_adapter

    register_adapter(EchoStubMCP())
    return True
