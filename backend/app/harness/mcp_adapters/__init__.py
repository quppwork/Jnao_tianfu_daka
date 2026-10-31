"""外部 MCP SDK 适配层 — 后续接第三方 MCP Server 时走这里。

现状：JNAO 主要自研 host/sandbox 工具。本包提供：
- ExternalMCPClient 协议（list_tools / call_tool）
- AdapterRegistry 注册远端服务器
- 把远端 tool 描述桥成与本地一致的 name/description/inputSchema

真正跑通外部 SDK 时：实现一个 Adapter 包装官方 client，register_adapter 即可。
"""

from app.harness.mcp_adapters.base import ExternalMCPClient, ExternalToolDesc, RemoteCallResult
from app.harness.mcp_adapters.registry import (
    AdapterRegistry,
    get_adapter_registry,
    register_adapter,
)

__all__ = [
    "AdapterRegistry",
    "ExternalMCPClient",
    "ExternalToolDesc",
    "RemoteCallResult",
    "get_adapter_registry",
    "register_adapter",
]
