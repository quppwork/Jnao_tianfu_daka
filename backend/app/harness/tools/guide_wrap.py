"""把 Guide 已有只读工具挂到 MCP（Mode B，查业务库）。"""

from __future__ import annotations

from typing import Any, Callable

from app.harness.context import current_context
from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_GUIDE: list[tuple[str, str, str, dict]] = (
    ("get_profile", "get_profile", "孩子昵称/学段/天赋摘要（只读）。", {}),
    ("get_today_plan", "get_today_plan", "今日训练是否有方案、计划时长、完成计数（不展开排课逻辑）。", {}),
    (
        "get_checkin_timeline",
        "get_checkin_timeline",
        "近几日打卡时间线。",
        {"limit": {"type": "integer"}},
    ),
    ("get_skill_progress", "get_skill_progress", "技能进度摘要。", {}),
    ("suggest_next_action", "suggest_next_action", "下一步建议（训练/测评/答疑）。", {}),
    ("get_talent_report_summary", "get_talent_report_summary", "有效天赋报告轻量摘要。", {}),
)


def _handler(guide_name: str) -> Callable:
    def run(args: dict[str, Any]) -> dict[str, Any]:
        ctx = current_context()
        if ctx.db is None or ctx.child_user_id < 1:
            return {"ok": False, "error": "需要 child_user_id 与数据库会话"}
        from app.agents.guide.tools import call_tool as guide_call, list_tools

        list_tools()
        raw = guide_call(ctx.db, ctx.child_user_id, guide_name, args)
        if isinstance(raw, dict):
            if "ok" not in raw:
                return {"ok": True, **raw}
            return raw
        return {"ok": True, "result": raw}

    return run


def register() -> None:
    for name, guide_name, desc, extra_props in _GUIDE:
        props = {"child_user_id": {"type": "integer", "description": "孩子 user id"}}
        props.update(extra_props)
        register_tool(
            ToolSpec(
                name=name,
                description=desc,
                input_schema={
                    "type": "object",
                    "properties": props,
                    "additionalProperties": True,
                },
                handler=_handler(guide_name),
                permission="readonly",
                profiles=("guide", "parent_guide"),
                plane="host",
                mcp_server="jnao-host",
                needs_db=True,
            )
        )
