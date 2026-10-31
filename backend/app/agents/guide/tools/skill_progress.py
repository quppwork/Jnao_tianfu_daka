"""工具：分技能进度（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.guide.tools import register


@register("get_skill_progress")
def get_skill_progress(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    from app.db.models import ChildUser
    from app.services.child_training_state import (
        get_training_progress,
        overall_tier,
    )

    child = db.get(ChildUser, child_user_id)
    if not child:
        return {"skills": {}, "overall_tier": 1, "training_days": 0}

    state = get_training_progress(child)
    skills_out = {}
    for sk, sd in (state.get("skills") or {}).items():
        if not isinstance(sd, dict):
            continue
        # 仅暴露档位快照；不返回 consecutive_pass / part 等内部计数
        skills_out[sk] = {
            "tier": int(sd.get("tier") or 1),
        }
    return {
        "overall_tier": overall_tier(state),
        "training_days": int(state.get("training_days") or 0),
        "skills": skills_out,
        "hint": "仅档位快照；回答时勿解释晋级条件、达标次数或内部计数",
    }
