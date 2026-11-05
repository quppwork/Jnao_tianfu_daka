"""Harness 状态 + MCP HTTP（本地默认开；生产须 HARNESS_MCP_HTTP=1）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.harness.mcp_protocol import handle_rpc
from app.harness.runtime import call_tool, harness_status
from app.harness.settings import load_harness_settings, mcp_http_enabled

router = APIRouter(prefix="/api/harness", tags=["harness"])


def _check_mcp_auth(authorization: str | None) -> None:
    from app.core.security import is_production

    token = load_harness_settings().mcp_token
    if not is_production() and not token:
        return
    if not token:
        raise HTTPException(503, "HARNESS_MCP_TOKEN 未配置")
    got = (authorization or "").strip()
    if got.startswith("Bearer "):
        got = got[7:].strip()
    if got != token:
        raise HTTPException(401, "invalid harness token")


@router.get("/status")
def status():
    return harness_status()


@router.get("/sandbox")
def sandbox_control():
    st = harness_status()
    return {
        "control_plane": st.get("control_plane"),
        "data_plane": st.get("data_plane"),
    }


@router.post("/tools/{name:path}")
async def invoke_tool(
    name: str,
    body: dict[str, Any] | None = None,
    authorization: str | None = Header(default=None),
):
    if not mcp_http_enabled():
        raise HTTPException(404, "harness mcp http disabled")
    _check_mcp_auth(authorization)
    args = body.get("arguments") if isinstance(body, dict) else {}
    if not isinstance(args, dict):
        args = body if isinstance(body, dict) else {}
    profile = None
    if isinstance(body, dict):
        profile = body.get("profile")
    result = await call_tool(name, args, profile=profile)
    return result.to_audit() | {"data": result.data}


@router.post("/mcp")
async def mcp_http(
    request: Request,
    authorization: str | None = Header(default=None),
):
    if not mcp_http_enabled():
        raise HTTPException(404, "harness mcp http disabled")
    _check_mcp_auth(authorization)
    body = await request.json()
    profile = request.headers.get("X-Harness-Profile")
    reply = await handle_rpc(body, profile=profile)
    if reply is None:
        return {"ok": True}
    return reply


@router.post("/agent/run")
async def agent_run(
    body: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    if not mcp_http_enabled():
        raise HTTPException(404, "harness mcp http disabled")
    _check_mcp_auth(authorization)
    from app.harness.context import context_from_args
    from app.harness.loop import run_agent

    profile = str(body.get("profile") or "harness")
    message = str(body.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message required")
    ctx = context_from_args(body, profile=profile)
    state = await run_agent(
        profile=profile,
        user_message=message,
        thread_id=body.get("thread_id"),
        ctx=ctx,
        max_steps=int(body.get("max_steps") or 6),
    )
    return state.to_public()


@router.post("/agent/resume")
async def agent_resume(
    body: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    if not mcp_http_enabled():
        raise HTTPException(404, "harness mcp http disabled")
    _check_mcp_auth(authorization)
    from app.harness.loop import run_agent

    tid = str(body.get("thread_id") or "").strip()
    if not tid:
        raise HTTPException(400, "thread_id required")
    tokens = body.get("confirm_tokens") or []
    if body.get("confirm_token"):
        tokens = list(tokens) + [str(body.get("confirm_token"))]
    state = await run_agent(
        profile=str(body.get("profile") or "harness"),
        user_message="",
        thread_id=tid,
        resume_tokens=[str(t) for t in tokens if t],
    )
    return state.to_public()
