"""MCP JSON-RPC 最小子集：initialize / tools/list / tools/call / ping。"""

from __future__ import annotations

from typing import Any

from app.harness.catalog import mcp_tool_list as catalog_mcp_tool_list
from app.harness.runtime import call_tool
from app.harness.settings import load_harness_settings

PROTOCOL = "2024-11-05"


async def handle_rpc(body: dict[str, Any], *, profile: str | None = None) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return _err(None, -32600, "invalid request")
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    if method and str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        cfg = load_harness_settings()
        return _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": cfg.server_name,
                    "version": cfg.server_version,
                },
            },
        )
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/list":
        return _ok(req_id, {"tools": catalog_mcp_tool_list(profile=profile)})
    if method == "tools/call":
        name = str(params.get("name") or "").strip()
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        if not name:
            return _err(req_id, -32602, "name required")
        result = await call_tool(name, args, profile=profile)
        return _ok(req_id, result.to_mcp_content())
    return _err(req_id, -32601, f"method not found: {method}")


def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
