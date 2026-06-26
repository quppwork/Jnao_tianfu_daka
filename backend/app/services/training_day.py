"""训练日边界 — 当日 04:00 至次日 03:59:59 为同一训练日"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

TZ = timezone(timedelta(hours=8))
RESET_HOUR = 4
NEW_DAY_GRACE_MINUTES = 5


def training_now() -> datetime:
    return datetime.now(TZ)


def get_training_day(now: datetime | None = None) -> date:
    now = now or training_now()
    if now.hour < RESET_HOUR:
        return now.date() - timedelta(days=1)
    return now.date()


def next_unlock_at(now: datetime | None = None) -> datetime:
    now = now or training_now()
    day = get_training_day(now)
    return datetime.combine(day + timedelta(days=1), time(RESET_HOUR, 0), tzinfo=TZ)


def plan_cutoff_at(plan_date: date) -> datetime:
    """某训练日方案的全局截止时刻（次日凌晨 4:00）"""
    return datetime.combine(plan_date + timedelta(days=1), time(RESET_HOUR, 0), tzinfo=TZ)


def plan_new_day_at(plan_date: date) -> datetime:
    """截止后 5 分钟可加载新一天方案"""
    return plan_cutoff_at(plan_date) + timedelta(minutes=NEW_DAY_GRACE_MINUTES)


def is_in_day_transition(now: datetime | None = None) -> bool:
    """凌晨 4:00–4:05 日切冻结窗口"""
    now = now or training_now()
    start = datetime.combine(now.date(), time(RESET_HOUR, 0), tzinfo=TZ)
    end = start + timedelta(minutes=NEW_DAY_GRACE_MINUTES)
    return start <= now < end


def is_new_day_ready(now: datetime | None = None) -> bool:
    """日切窗口结束后才可展示/创建新一天方案"""
    return not is_in_day_transition(now)


def is_plan_stale(plan, *, now: datetime | None = None) -> bool:
    """昨日方案或日切窗口内不应再展示"""
    if not plan:
        return True
    now = now or training_now()
    td = get_training_day(now)
    if plan.plan_date < td:
        return True
    if is_in_day_transition(now):
        return True
    return False


def is_plan_globally_cutoff(plan, *, now: datetime | None = None) -> bool:
    """方案已过全局凌晨 4 点截止（不论用户何时开始训练）"""
    if not plan:
        return False
    now = now or training_now()
    return now >= plan_cutoff_at(plan.plan_date)


def training_day_meta(now: datetime | None = None, *, plan_date: date | None = None) -> dict:
    now = now or training_now()
    td = get_training_day(now)
    unlock = next_unlock_at(now)
    ref_day = plan_date or td
    cutoff = plan_cutoff_at(ref_day)
    new_day = plan_new_day_at(ref_day)
    in_transition = is_in_day_transition(now)
    return {
        "training_day": td.isoformat(),
        "server_now": now.isoformat(),
        "unlock_at": unlock.isoformat(),
        "seconds_until_unlock": max(0, int((unlock - now).total_seconds())),
        "cutoff_at": cutoff.isoformat(),
        "new_day_at": new_day.isoformat(),
        "seconds_until_cutoff": max(0, int((cutoff - now).total_seconds())),
        "seconds_until_new_day": max(0, int((new_day - now).total_seconds())),
        "day_transition": in_transition,
        "new_day_ready": is_new_day_ready(now),
    }


def is_plan_day_locked(plan, *, now: datetime | None = None) -> bool:
    """当前训练日内方案已全部完成 → 全局锁定至次日凌晨 4 点"""
    if not plan or plan.status != "completed":
        return False
    now = now or training_now()
    return plan.plan_date == get_training_day(now)
