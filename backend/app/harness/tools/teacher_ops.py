"""老师端 MCP — 学院目录/进度只读；写操作走确认且暂不落库（无独立 LMS 表）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.harness.context import current_context
from app.harness.registry import register_tool
from app.harness.types import ToolSpec

_TEACHER = ("teacher", "harness")


def list_academy_courses(_args: dict[str, Any]) -> dict[str, Any]:
    from app.agents.academy.catalog import ACTS, EPISODES

    courses = [
        {
            "id": ep.id,
            "title": ep.title,
            "topic": ep.topic,
            "task": ep.task,
        }
        for ep in list(EPISODES.values())[:40]
    ]
    acts = [{"no": a.no, "name": a.name, "range": a.range, "locked": a.locked} for a in ACTS]
    return {"ok": True, "courses": courses, "acts": acts}


def list_course_participants(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    parent_id = ctx.parent_user_id or int(args.get("parent_id") or 0)
    if ctx.db is None or parent_id < 1:
        return {"ok": False, "error": "需要 parent_id，拒绝全库枚举学员"}
    from app.services.parent_service import list_children

    try:
        items = list_children(ctx.db, parent_id)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "parent_id": parent_id, "participants": items}


def list_course_learning_durations(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    if ctx.db is None or ctx.child_user_id < 1:
        return {"ok": False, "error": "需要 child_user_id"}
    from app.db.models import AcademyProgress, TrainingRecord

    rows = list(
        ctx.db.scalars(
            select(AcademyProgress).where(
                AcademyProgress.child_user_id == ctx.child_user_id
            )
        ).all()
    )
    academy = [
        {"episode_id": r.episode_id, "percent": r.percent, "unlocked": bool(r.unlocked)}
        for r in rows
    ]
    rec_n = ctx.db.scalar(
        select(func.count()).select_from(TrainingRecord).where(
            TrainingRecord.child_user_id == ctx.child_user_id
        )
    ) or 0
    return {
        "ok": True,
        "child_user_id": ctx.child_user_id,
        "academy_progress": academy,
        "training_record_count": int(rec_n),
    }


def list_course_learning_tasks(args: dict[str, Any]) -> dict[str, Any]:
    ctx = current_context()
    if ctx.db is None or ctx.child_user_id < 1:
        return {"ok": False, "error": "需要 child_user_id"}
    from app.agents.guide.tools import call_tool as guide_call, list_tools

    list_tools()
    plan = guide_call(ctx.db, ctx.child_user_id, "get_today_plan", {})
    return {"ok": True, "tasks_from": "today_plan", "plan": plan}


def _write_stub(kind: str):
    def run(args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "error": f"{kind} 未接业务写库（学院目录目前是代码目录，不是 LMS）",
            "proposed": {k: args.get(k) for k in list(args)[:8] if k != "confirmed"},
        }

    return run


def register() -> None:
    ro = dict(
        permission="readonly",
        profiles=_TEACHER,
        plane="host",
        mcp_server="jnao-teacher",
        needs_db=False,
    )
    register_tool(
        ToolSpec(
            name="list_academy_courses",
            description="列出天赋学院剧集/幕次目录（只读代码目录）。",
            input_schema={"type": "object", "properties": {}},
            handler=list_academy_courses,
            **ro,
        )
    )
    register_tool(
        ToolSpec(
            name="list_course_participants",
            description="按家长列出绑定学员。必须带 parent_id，禁止全库扫描。",
            input_schema={
                "type": "object",
                "properties": {"parent_id": {"type": "integer"}},
                "required": ["parent_id"],
            },
            handler=list_course_participants,
            permission="readonly",
            profiles=_TEACHER,
            plane="host",
            mcp_server="jnao-teacher",
            needs_db=True,
        )
    )
    register_tool(
        ToolSpec(
            name="list_course_learning_durations",
            description="某孩子学院观看进度与打卡记录条数。",
            input_schema={
                "type": "object",
                "properties": {"child_user_id": {"type": "integer"}},
            },
            handler=list_course_learning_durations,
            permission="readonly",
            profiles=_TEACHER,
            plane="host",
            mcp_server="jnao-teacher",
            needs_db=True,
        )
    )
    register_tool(
        ToolSpec(
            name="list_course_learning_tasks",
            description="某孩子今日训练任务摘要（不展开排课公式）。",
            input_schema={
                "type": "object",
                "properties": {"child_user_id": {"type": "integer"}},
            },
            handler=list_course_learning_tasks,
            permission="readonly",
            profiles=_TEACHER,
            plane="host",
            mcp_server="jnao-teacher",
            needs_db=True,
        )
    )
    wr = dict(
        permission="confirm",
        profiles=_TEACHER,
        plane="host",
        mcp_server="jnao-teacher",
        needs_db=False,
    )
    for name, desc in (
        ("create_course", "创建课程（需确认；当前无 LMS 表，确认后仍拒绝落库）。"),
        ("add_course_section", "给课程加小节（需确认；当前不落库）。"),
        ("upload_course_resource", "上传课程资源（需确认；当前不落库）。"),
    ):
        register_tool(
            ToolSpec(
                name=name,
                description=desc,
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "confirmed": {"type": "boolean"},
                    },
                    "additionalProperties": True,
                },
                handler=_write_stub(name),
                **wr,
            )
        )
