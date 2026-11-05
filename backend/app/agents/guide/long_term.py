"""长期摘要 — 仅从 DB 汇总节奏/弱项/时长偏好，不读聊天记忆。"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingPlan, TrainingRecord


@dataclass
class LongTermSummary:
    checkin_streak: int = 0
    checkins_last_14d: int = 0
    weak_skills: list[str] = field(default_factory=list)
    preferred_minutes: int | None = None
    total_checkins: int = 0

    def is_empty(self) -> bool:
        return (
            self.total_checkins <= 0
            and not self.weak_skills
            and self.preferred_minutes is None
            and self.checkin_streak <= 0
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        """空摘要返回空串，调用方应跳过注入。"""
        if self.is_empty():
            return ""
        lines = ["长期摘要（DB，勿编造）:"]
        lines.append(f"累计打卡: {self.total_checkins} 次")
        lines.append(f"连续打卡: {self.checkin_streak} 天")
        lines.append(f"近14日有打卡天数: {self.checkins_last_14d}")
        if self.weak_skills:
            lines.append(f"相对弱项技能: {', '.join(self.weak_skills)}")
        if self.preferred_minutes is not None:
            lines.append(f"常用训练时长: {self.preferred_minutes} 分钟")
        return "\n".join(lines)


def _checkin_streak(dates: list[date], *, today: date) -> int:
    """对齐 growth_service：允许今日未打卡则从昨天起算。"""
    if not dates:
        return 0
    date_set = set(dates)
    start = today if today in date_set else today - timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    cursor = start
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _distinct_checkin_dates(db: Session, child_user_id: int) -> list[date]:
    rows = db.scalars(
        select(TrainingRecord.train_date)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.train_date.is_not(None),
        )
        .distinct()
    ).all()
    return [d for d in rows if isinstance(d, date)]


def _weak_skills(
    child: ChildUser | None,
    *,
    limit: int = 2,
    has_training_signal: bool = False,
) -> list[str]:
    """无训练信号时不标弱项（避免默认 Tier=1 伪弱项）。"""
    if not child or not has_training_signal:
        return []
    from app.services.child_training_state import get_training_progress

    skills = get_training_progress(child).get("skills") or {}
    ranked: list[tuple[int, str]] = []
    for name, sd in skills.items():
        if not isinstance(sd, dict):
            continue
        ranked.append((int(sd.get("tier") or 1), str(name)))
    if not ranked:
        return []
    ranked.sort(key=lambda x: (x[0], x[1]))
    return [name for _, name in ranked[:limit]]


def _preferred_minutes(db: Session, child_user_id: int) -> int | None:
    plans = db.scalars(
        select(TrainingPlan)
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.planned_minutes.is_not(None),
        )
        .order_by(TrainingPlan.plan_date.desc(), TrainingPlan.id.desc())
        .limit(7)
    ).all()
    mins = [int(p.planned_minutes) for p in plans if p.planned_minutes]
    if not mins:
        return None
    # 众数；并列取较大时长
    counts = Counter(mins)
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def build_long_term_summary(
    db: Session,
    child_user_id: int,
    *,
    training_day: date | str | None = None,
) -> LongTermSummary:
    """从打卡记录 / 方案 / 技能进度汇总长期摘要。"""
    if isinstance(training_day, str):
        today = date.fromisoformat(training_day)
    elif isinstance(training_day, date):
        today = training_day
    else:
        from app.services.dev_clock import resolve_training_now
        from app.services.training_day import get_training_day

        today = get_training_day(resolve_training_now(db, child_user_id))

    dates = _distinct_checkin_dates(db, child_user_id)
    total = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0

    window_start = today - timedelta(days=13)
    last_14 = len({d for d in dates if window_start <= d <= today})

    child = db.get(ChildUser, child_user_id)
    training_days = 0
    if child:
        from app.services.child_training_state import get_training_progress

        training_days = int(get_training_progress(child).get("training_days") or 0)
    has_signal = int(total) > 0 or training_days > 0

    return LongTermSummary(
        checkin_streak=_checkin_streak(dates, today=today),
        checkins_last_14d=last_14,
        weak_skills=_weak_skills(child, has_training_signal=has_signal),
        preferred_minutes=_preferred_minutes(db, child_user_id),
        total_checkins=int(total),
    )


def build_daily_snapshot(
    ctx,
    long_term: LongTermSummary | None = None,
) -> dict[str, Any]:
    """与 bootstrap 缓存合流的当日情境快照。"""
    snap: dict[str, Any] = {
        "has_assessment": bool(getattr(ctx, "has_assessment", False)),
        "days_since_last_checkin": getattr(ctx, "days_since_last_checkin", None),
        "today_started": bool(getattr(getattr(ctx, "today", None), "has_started", False)),
        "today_status": getattr(getattr(ctx, "today", None), "status", None),
        "situation": getattr(ctx, "situation", None),
        "next_action": getattr(ctx, "next_action", None),
    }
    if long_term is not None and not long_term.is_empty():
        snap["long_term"] = {
            "checkin_streak": long_term.checkin_streak,
            "checkins_last_14d": long_term.checkins_last_14d,
            "weak_skills": list(long_term.weak_skills),
            "preferred_minutes": long_term.preferred_minutes,
            "total_checkins": long_term.total_checkins,
        }
    return snap
