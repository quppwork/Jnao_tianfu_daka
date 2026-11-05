"""工具：打卡时间线摘要（只读）。"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.agents.guide.tools import register

_MAX_LIMIT = 30


@register("get_checkin_timeline")
def get_checkin_timeline(db: Session, child_user_id: int, args: dict) -> dict:
    raw_limit = int(args.get("limit") or 14)
    limit = max(1, min(raw_limit, _MAX_LIMIT))

    from app.services.training_service import get_checkin_history

    items = get_checkin_history(db, child_user_id, limit=limit)
    by_day: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "skills": set()}
    )
    for it in items:
        day = it.get("train_date") or "unknown"
        if hasattr(day, "isoformat"):
            day = day.isoformat()
        day = str(day)
        by_day[day]["count"] += 1
        skill = (it.get("ability_type") or it.get("skill") or "").strip()
        if skill:
            by_day[day]["skills"].add(skill)

    days = []
    for day in sorted(by_day.keys(), reverse=True):
        row = by_day[day]
        days.append({
            "date": day,
            "count": row["count"],
            "skills": sorted(row["skills"])[:8],
        })

    return {
        "child_user_id": child_user_id,
        "limit": limit,
        "total_records": len(items),
        "days": days[:14],
    }
