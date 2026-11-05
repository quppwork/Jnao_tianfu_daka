"""Agent 工具：读取本份天赋测评报告摘要（本地 report_json）。

后续若有独立「获取报告内容」HTTP/上游接口，可在此 handler 内替换数据源；
对外工具名与入参保持稳定，供 report_talent Agent 先取报告再拼 knowledge_qa 问句。
"""

from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec


async def get_report_content(args: dict[str, Any]) -> dict[str, Any]:
    from app.harness.context import current_context
    from app.services.report_talent_context import build_report_context

    ctx = current_context()
    db = ctx.db
    assessment_id = int(
        (args or {}).get("assessment_id")
        or (ctx.extra or {}).get("assessment_id")
        or 0
    )
    section = str((args or {}).get("section") or "").strip()
    if not db or assessment_id <= 0:
        return {
            "ok": False,
            "error": "缺少 assessment_id 或 db 上下文",
            "error_kind": "input",
        }

    from app.db.models import TalentAssessment

    row = db.get(TalentAssessment, assessment_id)
    if row is None:
        return {"ok": False, "error": "报告不存在", "error_kind": "not_found"}

    report = row.report_json if isinstance(row.report_json, dict) else {}
    summary = build_report_context(report, getattr(row, "talent_primary", None))
    if not summary:
        return {
            "ok": False,
            "error": "报告暂无可用正文",
            "error_kind": "empty",
            "assessment_id": assessment_id,
        }

    # section 预留：整份 / 按关键词截取一段，供 Agent 只问报告某一块
    body = summary
    if section and section not in ("全部", "整份", "all", "full"):
        lines = [ln for ln in summary.splitlines() if section in ln]
        if lines:
            body = "\n".join(lines)

    return {
        "ok": True,
        "assessment_id": assessment_id,
        "talent_primary": getattr(row, "talent_primary", None) or "",
        "section": section or "全部",
        "content": body,
    }


SPEC = ToolSpec(
    name="get_report_content",
    description=(
        "读取用户当前这份天赋测评报告的摘要（五者/五维/状态等）。"
        "用户问「我的报告 / 这份报告怎么看 / 报告里某某」时先调本工具，"
        "再把 content 与用户原问一并交给 knowledge_qa。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "assessment_id": {
                "type": "integer",
                "description": "测评 ID；缺省用当前 ToolContext",
            },
            "section": {
                "type": "string",
                "description": "可选：全部，或关键词如 五维/学者/状态",
            },
        },
        "additionalProperties": False,
    },
    handler=get_report_content,
    isolation="none",
    permission="readonly",
    needs_db=True,
    profiles=("report_talent",),
    plane="host",
    mcp_server="jnao-host",
)


def register() -> None:
    register_tool(SPEC)


register()
