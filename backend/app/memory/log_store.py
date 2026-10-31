"""历史记录全量落盘 — 即 ThreadStore（按 domain 分表）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.memory.sql_store import SqlThreadStore, get_thread_store


def get_log_store(db: Session) -> SqlThreadStore:
    """持久会话日志入口（对照 log-store.js）。"""
    return get_thread_store(db)
