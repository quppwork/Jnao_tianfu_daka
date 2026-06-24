"""清空本地业务数据（保留 content_item 音频资源库）

用法:
  python scripts/reset_local_data.py
  python scripts/reset_local_data.py --all   # 连音频目录也清空
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)

from sqlalchemy import delete, func, select, text

from app.db.models import (
    ChildUser,
    ContentItem,
    GuideMessage,
    GuideSession,
    QaMessage,
    QaSession,
    TalentAssessment,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
)
from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_catalog


def reset_db(*, include_content: bool = False) -> dict[str, int]:
    init_db()
    session = get_session_factory()()
    counts: dict[str, int] = {}
    try:
        for model in (
            GuideMessage,
            GuideSession,
            QaMessage,
            QaSession,
            TrainingRecord,
            TrainingItem,
            TrainingPlan,
            TrainingWindow,
            TalentAssessment,
            ChildUser,
        ):
            name = model.__tablename__
            counts[name] = session.scalar(select(func.count()).select_from(model)) or 0
            session.execute(delete(model))

        if include_content:
            counts["content_item"] = session.scalar(select(func.count()).select_from(ContentItem)) or 0
            session.execute(delete(ContentItem))
            session.commit()
            imported = import_catalog(session, replace=False)
            counts["content_item_imported"] = imported
        else:
            session.commit()
    finally:
        session.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset local MySQL business data")
    parser.add_argument("--all", action="store_true", help="Also wipe and re-import content_item")
    args = parser.parse_args()

    before = reset_db(include_content=args.all)
    print("已清空本地 MySQL 业务数据:")
    for table, n in before.items():
        if table != "content_item_imported":
            print(f"  {table}: {n} 条")
    if args.all and "content_item_imported" in before:
        print(f"  content_item 重新导入: {before['content_item_imported']} 条")
    print()
    print("请在浏览器执行（F12 控制台）或刷新后手动清 localStorage:")
    print("  localStorage.clear(); location.reload()")


if __name__ == "__main__":
    main()
