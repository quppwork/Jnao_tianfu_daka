"""共享线程池 — 把同步 HTTP/SDK 从 asyncio 事件循环挪开。"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_workers = max(4, int(os.getenv("SYNC_IO_THREAD_WORKERS", "16") or 16))
_executor = ThreadPoolExecutor(max_workers=_workers, thread_name_prefix="sync-io")


async def run_sync(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """在专用线程池执行同步函数，避免堵死 uvicorn 事件循环。"""
    loop = asyncio.get_running_loop()
    if kwargs:
        call = partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_executor, call)
    return await loop.run_in_executor(_executor, fn, *args)
