"""MCP 聚合层：按 plane 分成宿主服务器 / 沙箱服务器，对外只暴露策略允许的工具。"""

from __future__ import annotations

from typing import Any

from app.harness.policy import visible_specs
from app.harness.registry import list_tool_specs
from app.harness.types import ToolSpec

SERVERS = (
    {
        "name": "jnao-host",
        "plane": "host",
        "mode": "B",
        "description": "凭证类工具在沙箱外（百炼 Retrieve 等），密钥不进沙箱",
    },
    {
        "name": "jnao-sandbox",
        "plane": "sandbox",
        "mode": "A",
        "description": "隔离执行在沙箱内；宿主只走 JSON stdio，不监听对外端口",
    },
    {
        "name": "jnao-teacher",
        "plane": "host",
        "mode": "B",
        "description": "老师端学院目录/进度只读；写操作需确认且当前不落 LMS 库",
    },
)


def tools_for_server(server: str, *, profile: str | None = None) -> list[ToolSpec]:
    specs = [t for t in list_tool_specs(profile=None) if t.mcp_server == server]
    return visible_specs(specs, profile=profile)


def aggregated_tools(*, profile: str | None = None) -> list[ToolSpec]:
    return visible_specs(list_tool_specs(profile=None), profile=profile)


def mcp_tool_list(*, profile: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
            "plane": t.plane,
            "server": t.mcp_server,
        }
        for t in aggregated_tools(profile=profile)
    ]


def catalog_status() -> dict[str, Any]:
    return {
        "servers": [
            {
                **row,
                "tools": [t.name for t in tools_for_server(str(row["name"]))],
            }
            for row in SERVERS
        ],
        "note": "沙箱不直连全部 MCP；只连本聚合层。Mode A 无 loopback 监听，stdio 比 curl-to-127.0.0.1 更窄。",
    }
