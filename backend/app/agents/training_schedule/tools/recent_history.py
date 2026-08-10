"""工具：近史技能摘要（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx


@register("get_recent_training_history")
def get_recent_training_history(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id
    ctx = get_request_ctx()
    days = int(args.get("days") or 7)
    days = max(1, min(days, 14))
    recent = list(ctx.history[-days:])
    entries = []
    skill_freq: dict[str, int] = {}
    for h in recent:
        sks = list(h.skills or ())
        entries.append({
            "date": str(h.plan_date),
            "minutes": h.planned_minutes,
            "skills": sks,
        })
        for sk in sks:
            skill_freq[sk] = skill_freq.get(sk, 0) + 1
    return {
        "days": days,
        "entries": entries,
        "skill_frequency": skill_freq,
        "hint": "频率高的技能可适当后置，但仍须从可选列表中选",
    }
