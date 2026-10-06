"""家长线只读工具 — 看板、会话、周报材料。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.harness.context import current_context
from app.harness.registry import register_tool
from app.harness.types import ToolSpec


def get_progress_dashboard(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    parent_id = ctx.parent_user_id or ctx.actor_user_id
    child_id = ctx.child_user_id
    if ctx.db is None or parent_id < 1 or child_id < 1:
        return {"ok": False, "error": "需要 parent_id 与 child_user_id"}
    from app.services.parent_dashboard_service import get_dashboard

    board = get_dashboard(ctx.db, parent_id, child_id)
    return {"ok": True, "dashboard": board}


def conversation_history_get(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    if ctx.db is None or ctx.child_user_id < 1:
        return {"ok": False, "error": "需要 child_user_id"}
    from app.db.models import GuideMessage, GuideSession

    limit = min(30, max(1, int(args.get("limit") or 12)))
    sess = ctx.db.scalars(
        select(GuideSession)
        .where(GuideSession.child_user_id == ctx.child_user_id)
        .order_by(GuideSession.id.desc())
    ).first()
    if not sess:
        return {"ok": True, "items": []}
    rows = list(
        ctx.db.scalars(
            select(GuideMessage)
            .where(GuideMessage.session_id == sess.id)
            .order_by(GuideMessage.id.desc())
            .limit(limit)
        ).all()
    )
    rows.reverse()
    items = [
        {"role": m.role, "content": (m.content or "")[:400], "id": m.id} for m in rows
    ]
    return {"ok": True, "session_id": sess.id, "items": items}


def conversation_search(args: dict[str, Any]) -> dict[str, Any]:
    q = str(args.get("query") or "").strip()
    hist = conversation_history_get({"limit": 30})
    if not hist.get("ok"):
        return hist
    if not q:
        return hist
    items = [x for x in hist.get("items") or [] if q in (x.get("content") or "")]
    return {"ok": True, "query": q, "items": items[:12]}


def completion_report(args: dict[str, Any]) -> dict[str, Any]:
    dash = get_progress_dashboard(args)
    if not dash.get("ok"):
        return dash
    board = dash.get("dashboard") or {}
    return {
        "ok": True,
        "kind": "completion_report",
        "summary": {
            "nickname": (board.get("child") or {}).get("nickname"),
            "week_minutes": ((board.get("metrics") or {}).get("week_minutes") or {}),
            "tier": (board.get("tier") or {}).get("duan_label"),
        },
        "dashboard": board,
    }


def generate_revision_plan(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    if ctx.db is None or ctx.child_user_id < 1:
        return {"ok": False, "error": "需要 child_user_id"}
    from app.agents.guide.tools import call_tool as guide_call, list_tools

    list_tools()
    nxt = guide_call(ctx.db, ctx.child_user_id, "suggest_next_action", {})
    today = guide_call(ctx.db, ctx.child_user_id, "get_today_plan", {})
    return {"ok": True, "next": nxt, "today": today}


def register() -> None:
    common = {
        "permission": "readonly",
        "profiles": ("parent_guide", "consult"),
        "plane": "host",
        "mcp_server": "jnao-host",
        "needs_db": True,
    }
    register_tool(
        ToolSpec(
            name="get_progress_dashboard",
            description="家长看板：本周时长、效率、段位等（只读，不编造分数）。",
            input_schema={
                "type": "object",
                "properties": {
                    "parent_id": {"type": "integer"},
                    "child_user_id": {"type": "integer"},
                },
                "additionalProperties": True,
            },
            handler=get_progress_dashboard,
            **common,
        )
    )
    register_tool(
        ToolSpec(
            name="conversation_history_get",
            description="读取该孩子最近一次引导会话消息（截断，只读）。",
            input_schema={
                "type": "object",
                "properties": {
                    "child_user_id": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
            },
            handler=conversation_history_get,
            **common,
        )
    )
    register_tool(
        ToolSpec(
            name="conversation_search",
            description="在该孩子引导会话里按关键字检索。",
            input_schema={
                "type": "object",
                "properties": {
                    "child_user_id": {"type": "integer"},
                    "query": {"type": "string"},
                },
            },
            handler=conversation_search,
            **common,
        )
    )
    register_tool(
        ToolSpec(
            name="completion_report",
            description="用看板数据生成完成情况摘要，不另起模型编造。",
            input_schema={
                "type": "object",
                "properties": {
                    "parent_id": {"type": "integer"},
                    "child_user_id": {"type": "integer"},
                },
            },
            handler=completion_report,
            **common,
        )
    )
    register_tool(
        ToolSpec(
            name="generate_revision_plan",
            description="根据今日方案与下一步建议拼复习计划材料。",
            input_schema={
                "type": "object",
                "properties": {"child_user_id": {"type": "integer"}},
            },
            handler=generate_revision_plan,
            **common,
        )
    )
