"""学院页只读孩子天赋档位。不写测评，不写训练。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from app.services.assessment_service import resolve_effective_talent
from app.services.child_training_state import display_overall_tier


def talent_badge(db: Session, user_id: int) -> tuple[str, str, int]:
    talent = resolve_effective_talent(db, user_id) or {}
    name = (talent.get("talent_primary") or "").strip()
    child = db.get(ChildUser, user_id)
    tier = int(display_overall_tier(db, child) or 1)
    if not name:
        return f"未测 · Lv.{tier}", "", tier
    return f"{name} · Lv.{tier}", name, tier
