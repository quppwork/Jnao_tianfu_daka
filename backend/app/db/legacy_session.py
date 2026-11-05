"""只读连接 db_fz_jingnao — 查询 ys_wx_member"""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@lru_cache(maxsize=1)
def get_legacy_engine() -> Engine | None:
    url = (os.getenv("LEGACY_DATABASE_URL") or "").strip()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)
