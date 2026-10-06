from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec


def sandbox_ping(args: dict[str, Any]) -> dict[str, Any]:
    # 实际执行在 sandbox_runner；此 handler 仅作 spec 占位。
    return {"ok": True, "pong": str(args.get("token") or "ok")}


SPEC = ToolSpec(
    name="sandbox.ping",
    description="探测 Harness 沙箱（本地子进程或 Docker 隔离容器）。",
    input_schema={
        "type": "object",
        "properties": {"token": {"type": "string"}},
        "additionalProperties": False,
    },
    handler=sandbox_ping,
    isolation="process",
    permission="readonly",
    profiles=("harness",),
    plane="sandbox",
    mcp_server="jnao-sandbox",
)


def register() -> None:
    register_tool(SPEC)


register()
