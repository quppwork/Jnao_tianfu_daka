#!/usr/bin/env python3
"""手动导入音频目录到 content_item（OSS play_url 写入 MySQL）

用法：
  本地:  cd backend && python ../scripts/import_catalog.py
  Docker: docker compose -f docker-compose.prod.yml exec backend python import_catalog.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_HERE, "..", "backend")
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

if not os.getenv("DATABASE_URL"):
    load_dotenv(os.path.join(_BACKEND, ".env"), override=False)
    _prod = os.path.join(_HERE, "..", ".env.production")
    if os.path.isfile(_prod):
        load_dotenv(_prod, override=False)

from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_all_xet_catalogs
from sqlalchemy import func, select
from app.db.models import ContentItem


def main() -> None:
    init_db()
    db = get_session_factory()()
    try:
        before = db.scalar(select(func.count()).select_from(ContentItem)) or 0
        results = import_all_xet_catalogs(db)
        after = db.scalar(select(func.count()).select_from(ContentItem)) or 0
        print(f"OK: content_item {before} -> {after}")
        for name, n in results.items():
            print(f"  {name}: {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
