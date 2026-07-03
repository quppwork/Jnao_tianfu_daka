"""Redis 缓存 — 无 REDIS_URL 时透明降级为直读 DB"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

_redis: Any = None
_redis_checked = False


def _json_default(obj: Any) -> str:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def ttl_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_client():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis

        _redis = redis.from_url(url, decode_responses=True)
        _redis.ping()
    except Exception:
        _redis = None
    return _redis


def cache_get_json(key: str) -> Any | None:
    client = get_client()
    if not client:
        return None
    raw = client.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        client.delete(key)
        return None


def cache_set_json(key: str, value: Any, ttl: int) -> None:
    client = get_client()
    if not client or ttl <= 0:
        return
    client.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=_json_default))


def cache_delete(key: str) -> None:
    client = get_client()
    if not client:
        return
    client.delete(key)


def cache_delete_prefix(prefix: str) -> None:
    client = get_client()
    if not client or not prefix:
        return
    for key in client.scan_iter(match=f"{prefix}*", count=100):
        client.delete(key)


def cache_get_or_load(key: str, ttl: int, loader: Any) -> Any:
    cached = cache_get_json(key)
    if cached is not None:
        return cached
    value = loader()
    if value is not None:
        cache_set_json(key, value, ttl)
    return value


# ── Key 规范 jnao:{模块}:{user_id}:... ──

def key_profile(user_id: int) -> str:
    return f"jnao:profile:{user_id}"


def key_assessment_latest(user_id: int) -> str:
    return f"jnao:assess:latest:{user_id}"


def key_growth(name: str, user_id: int) -> str:
    return f"jnao:growth:{name}:{user_id}"


def key_train_today(user_id: int, plan_date: date | str) -> str:
    return f"jnao:train:today:{user_id}:{plan_date}"


def key_train_progress(user_id: int) -> str:
    return f"jnao:train:progress:{user_id}"


def key_qa_sessions(user_id: int) -> str:
    return f"qa:sessions:{user_id}"


def invalidate_user_profile(user_id: int) -> None:
    cache_delete(key_profile(user_id))


def invalidate_user_assessment(user_id: int) -> None:
    cache_delete(key_assessment_latest(user_id))


def invalidate_user_growth(user_id: int) -> None:
    for name in ("summary", "badges", "milestones", "share"):
        cache_delete(key_growth(name, user_id))
    for limit in (40, 100):
        cache_delete(key_growth(f"timeline:{limit}", user_id))


def invalidate_user_training(user_id: int, plan_date: date | str | None = None) -> None:
    if plan_date is not None:
        cache_delete(key_train_today(user_id, plan_date))
    else:
        cache_delete_prefix(f"jnao:train:today:{user_id}:")
    cache_delete(key_train_progress(user_id))


def invalidate_user_read_caches(user_id: int, *, plan_date: date | str | None = None) -> None:
    """写操作后批量失效用户读缓存"""
    invalidate_user_profile(user_id)
    invalidate_user_assessment(user_id)
    invalidate_user_growth(user_id)
    invalidate_user_training(user_id, plan_date=plan_date)
