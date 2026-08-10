"""工具：提交技能草案（唯一「完成」动作；仍不写 DB）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx


@register("propose_skill_draft")
def propose_skill_draft(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id
    ctx = get_request_ctx()
    raw = args.get("skills") or []
    if not isinstance(raw, list):
        return {"ok": False, "error": "skills 必须是数组"}
    skills: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            skills.append(item.strip())
        elif isinstance(item, dict) and item.get("skill"):
            skills.append(str(item["skill"]).strip())
    if not skills:
        return {"ok": False, "error": "skills 不能为空"}
    allowed = set(ctx.available_skills)
    filtered = [s for s in skills if s in allowed]
    if not filtered:
        return {
            "ok": False,
            "error": "无一技能在 selectable_now 中",
            "selectable_now": list(ctx.available_skills),
            "target_slot_count": ctx.target_slot_count,
        }
    reason_raw = args.get("reason")
    reason = str(reason_raw).strip() if reason_raw is not None else ""
    if len(reason) > 500:
        reason = reason[:500]
    ctx.draft_skills = filtered
    ctx.draft_reason = reason or None
    ctx.draft_submitted = True
    return {
        "ok": True,
        "accepted_skills": filtered,
        "dropped": [s for s in skills if s not in filtered],
        "reason": ctx.draft_reason,
        "target_slot_count": ctx.target_slot_count,
        "hint": (
            f"草案已记录；服务层将按约 {ctx.target_slot_count} 项预算投影落库"
            "（意图优先补齐，规则仅作闸门）"
        ),
    }
