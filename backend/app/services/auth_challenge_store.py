"""验证码/短信挑战临时存储 — Redis 优先，无 Redis 时内存降级"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.core.cache import cache_delete, cache_get_json, cache_set_json, get_client

_mem: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()


def challenge_set(key: str, value: dict[str, Any], ttl: int) -> None:
    if ttl <= 0:
        return
    if get_client():
        cache_set_json(key, value, ttl)
        return
    with _lock:
        _mem[key] = (time.time() + ttl, value)


def challenge_get(key: str) -> dict[str, Any] | None:
    if get_client():
        return cache_get_json(key)
    with _lock:
        row = _mem.get(key)
        if not row:
            return None
        expire_at, value = row
        if time.time() > expire_at:
            _mem.pop(key, None)
            return None
        return value


def challenge_delete(key: str) -> None:
    if get_client():
        cache_delete(key)
        return
    with _lock:
        _mem.pop(key, None)


def challenge_incr(key: str, ttl: int) -> int:
    """计数器（限流用）"""
    current = challenge_get(key) or {"n": 0}
    n = int(current.get("n") or 0) + 1
    challenge_set(key, {"n": n}, ttl)
    return n


def challenge_get_count(key: str) -> int:
    row = challenge_get(key)
    return int(row.get("n") or 0) if row else 0
