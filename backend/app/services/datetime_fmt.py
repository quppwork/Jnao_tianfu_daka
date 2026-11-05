"""API 时间格式化 — 数据库存储 naive 北京时间"""

from __future__ import annotations

from datetime import datetime

from app.services.training_day import TZ


def format_cst(dt: datetime | None) -> str | None:
    """将 datetime 格式化为北京时间字符串 YYYY-MM-DD HH:mm"""
    if not dt:
        return None
    local = dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)
    return local.strftime("%Y-%m-%d %H:%M")
