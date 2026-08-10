"""工具：连打/断档与近史方案完成度（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.checkin_summary import build_rhythm_summary


@register("get_training_rhythm")
def get_training_rhythm(db: Session, child_user_id: int, args: dict) -> dict:
    ctx = get_request_ctx()
    days = int(args.get("days") or 14)
    return build_rhythm_summary(db, child_user_id, lookback_days=days)
