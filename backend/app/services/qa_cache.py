"""学科答疑会话列表 — Redis 缓存（无 REDIS_URL 时透明降级）"""

from __future__ import annotations

from app.core.cache import (
    cache_delete,
    cache_get_json,
    cache_set_json,
    key_qa_sessions,
    ttl_env,
)

_TTL = ttl_env("QA_SESSION_CACHE_TTL", 3600)


def get_session_list(user_id: int) -> list[dict] | None:
    data = cache_get_json(key_qa_sessions(user_id))
    return data if isinstance(data, list) else None


def set_session_list(user_id: int, items: list[dict]) -> None:
    cache_set_json(key_qa_sessions(user_id), items, _TTL)


def invalidate_session_list(user_id: int) -> None:
    cache_delete(key_qa_sessions(user_id))
