"""训练域公共：错误类型、缓存、日期时间、窗口判定"""

from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.core.cache import (
    cache_delete,
    cache_get_json,
    cache_set_json,
    key_train_today,
    ttl_env,
)
from app.services.training_day import get_training_day, training_now, TZ

_PLAN_CACHE_TTL = ttl_env("CACHE_TTL_TRAINING_TODAY", 30)

def invalidate_plan_cache(child_user_id: int, plan_date: date):
    """打卡、修改方案后立即清除该用户当日缓存"""
    cache_delete(key_train_today(child_user_id, plan_date))


def _cache_get(child_user_id: int, plan_date: date) -> dict | None:
    data = cache_get_json(key_train_today(child_user_id, plan_date))
    return data if isinstance(data, dict) else None


def _cache_set(child_user_id: int, plan_date: date, data: dict) -> None:
    cache_set_json(key_train_today(child_user_id, plan_date), data, _PLAN_CACHE_TTL)


def _invalidate_after_checkin_change(child_user_id: int, plan_date: date) -> None:
    from app.core.cache import (
        invalidate_user_growth,
        invalidate_user_guide,
        invalidate_user_training,
    )

    invalidate_plan_cache(child_user_id, plan_date)
    invalidate_user_growth(child_user_id)
    invalidate_user_training(child_user_id, plan_date=plan_date)
    invalidate_user_guide(child_user_id)


WATCH_COMPLETE_PCT = 90


def _user_now(db: Session | None, child_user_id: int | None = None):
    if db is not None and child_user_id is not None:
        from app.services.dev_clock import resolve_training_now

        return resolve_training_now(db, child_user_id)
    return training_now()


def _today() -> date:
    return get_training_day()


def _today_for(db: Session | None, child_user_id: int | None = None) -> date:
    return get_training_day(_user_now(db, child_user_id))

class TrainingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise TrainingError("时间格式应为 HH:MM")
    sec = int(parts[2]) if len(parts) > 2 else 0
    return time(int(parts[0]), int(parts[1]), sec)


def _format_time(value: time) -> str:
    return value.strftime("%H:%M:%S") if value.second else value.strftime("%H:%M")

def _time_in_training_window(start: time, end: time, current: time) -> bool:
    """训练窗口内判断，支持跨日（如 22:00→06:00）。"""
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end

