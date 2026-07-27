"""工具：平台可训练的能力列表（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.guide.tools import register


@register("get_training_courses")
def get_training_courses(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id, args
    from app.agents.shared.handoff import COURSE_LIST

    return {"courses": COURSE_LIST}
