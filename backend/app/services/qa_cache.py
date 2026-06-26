"""学科答疑会话列表 — 可选 Redis 缓存（无 REDIS_URL 时透明降级为直读 DB）"""

from __future__ import annotations

import json
import os
from typing import Any

_TTL = int(os.getenv("QA_SESSION_CACHE_TTL", "3600"))
_PREFIX = "qa:sessions:"

_redis: Any = None
_redis_checked = False


def _client():
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


def _key(user_id: int) -> str:
    return f"{_PREFIX}{user_id}"


def get_session_list(user_id: int) -> list[dict] | None:
    client = _client()
    if not client:
        return None
    raw = client.get(_key(user_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        client.delete(_key(user_id))
        return None


def set_session_list(user_id: int, items: list[dict]) -> None:
    client = _client()
    if not client:
        return
    client.setex(_key(user_id), _TTL, json.dumps(items, ensure_ascii=False))


def invalidate_session_list(user_id: int) -> None:
    client = _client()
    if not client:
        return
    client.delete(_key(user_id))
