"""工具：平台可训练的能力列表（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.guide.tools import register
from app.services.child_training_state import REQUIRED_SKILLS

# 选修常见项（只读目录；不写库）
_ELECTIVE_COURSES = ("多元感知", "精力恢复", "高效作业", "开口窍")


@register("get_training_courses")
def get_training_courses(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id, args
    courses = [
        {"name": name, "required": True}
        for name in REQUIRED_SKILLS
    ]
    courses.extend(
        {"name": name, "required": False}
        for name in _ELECTIVE_COURSES
    )
    return {"courses": courses}
