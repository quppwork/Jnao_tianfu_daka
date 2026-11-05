"""限流 — Redis 优先（多 worker 共享），不可用时降级进程内存。"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import date

from fastapi import HTTPException

_buckets: dict[str, list[float]] = defaultdict(list)


def reset_rate_limit_buckets() -> None:
    """测试用：清空内存桶。"""
    _buckets.clear()


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _check_rate_limit_memory(
    key: str,
    *,
    max_calls: int,
    window_sec: int,
    detail: str | None,
) -> None:
    now = time.time()
    bucket = [t for t in _buckets[key] if now - t < window_sec]
    if len(bucket) >= max_calls:
        raise HTTPException(
            429,
            detail or "请求过于频繁，请稍后再试",
        )
    bucket.append(now)
    _buckets[key] = bucket


def _check_rate_limit_redis(
    key: str,
    *,
    max_calls: int,
    window_sec: int,
    detail: str | None,
) -> bool:
    """成功走 Redis 返回 True；客户端不可用返回 False 以便降级。"""
    from app.core.cache import get_client

    client = get_client()
    if not client:
        return False
    rkey = f"rl:{key}"
    try:
        n = int(client.incr(rkey))
        if n == 1:
            client.expire(rkey, max(1, window_sec))
        if n > max_calls:
            raise HTTPException(
                429,
                detail or "请求过于频繁，请稍后再试",
            )
        return True
    except HTTPException:
        raise
    except Exception:
        return False


def check_rate_limit(
    key: str,
    *,
    max_calls: int,
    window_sec: int,
    detail: str | None = None,
) -> None:
    if max_calls <= 0:
        return
    if _check_rate_limit_redis(
        key, max_calls=max_calls, window_sec=window_sec, detail=detail
    ):
        return
    _check_rate_limit_memory(
        key, max_calls=max_calls, window_sec=window_sec, detail=detail
    )


def check_guide_chat_limits(child_user_id: int) -> None:
    """每用户 Guide 对话：短窗 QPS + 自然日配额。

    env:
      GUIDE_CHAT_RATE_LIMIT=0 关闭
      GUIDE_CHAT_QPS_MAX / GUIDE_CHAT_QPS_WINDOW_SEC
      GUIDE_CHAT_DAY_MAX
    """
    if os.getenv("GUIDE_CHAT_RATE_LIMIT", "1").strip() != "1":
        return
    uid = int(child_user_id)
    qps_max = _env_int("GUIDE_CHAT_QPS_MAX", 10)
    qps_win = _env_int("GUIDE_CHAT_QPS_WINDOW_SEC", 60)
    day_max = _env_int("GUIDE_CHAT_DAY_MAX", 150)

    check_rate_limit(
        f"guide:chat:{uid}",
        max_calls=qps_max,
        window_sec=max(1, qps_win),
        detail="说太快了，稍等再问老师",
    )
    day = date.today().isoformat()
    # 键已含日期；window 仅用于清理同键内过期时间戳
    check_rate_limit(
        f"guide:chat:day:{uid}:{day}",
        max_calls=day_max,
        window_sec=86400 * 2,
        detail="今天问得有点多了，明天再来找老师聊吧",
    )


def check_qa_chat_limits(child_user_id: int) -> None:
    """每用户学科答疑对话：短窗 QPS + 自然日配额（与 Guide 分桶，互不影响）。

    env:
      QA_CHAT_RATE_LIMIT=0 关闭
      QA_CHAT_QPS_MAX / QA_CHAT_QPS_WINDOW_SEC
      QA_CHAT_DAY_MAX
    """
    if os.getenv("QA_CHAT_RATE_LIMIT", "1").strip() != "1":
        return
    uid = int(child_user_id)
    qps_max = _env_int("QA_CHAT_QPS_MAX", 10)
    qps_win = _env_int("QA_CHAT_QPS_WINDOW_SEC", 60)
    day_max = _env_int("QA_CHAT_DAY_MAX", 150)

    check_rate_limit(
        f"qa:chat:{uid}",
        max_calls=qps_max,
        window_sec=max(1, qps_win),
        detail="问得太快了，稍等再问张宇老师",
    )
    day = date.today().isoformat()
    check_rate_limit(
        f"qa:chat:day:{uid}:{day}",
        max_calls=day_max,
        window_sec=86400 * 2,
        detail="今天答疑问得有点多了，明天再来吧",
    )
