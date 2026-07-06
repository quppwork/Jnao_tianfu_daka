"""简易内存限流 — 单进程有效；生产多 worker 建议配合 Redis。"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException

_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, *, max_calls: int, window_sec: int) -> None:
    now = time.time()
    bucket = [t for t in _buckets[key] if now - t < window_sec]
    if len(bucket) >= max_calls:
        raise HTTPException(429, "请求过于频繁，请稍后再试")
    bucket.append(now)
    _buckets[key] = bucket
