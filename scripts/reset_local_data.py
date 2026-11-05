"""清空业务数据；可选删表重建（服务器部署清库用）

用法:
  # 只清数据，保留表结构和 content_item 音频目录
  python scripts/reset_local_data.py

  # 连音频目录也清空并重新导入
  python scripts/reset_local_data.py --all

  # 删光所有表 + init_db 重建（服务器全新部署推荐）
  python scripts/reset_local_data.py --drop-rebuild -y

  # 删表重建 + 重新导入音频目录
  python scripts/reset_local_data.py --drop-rebuild --all -y

服务器示例:
  cd /path/to/Jnao_tianfu_daka
  git pull origin backend/dev
  python scripts/reset_local_data.py --drop-rebuild -y
  # 重启 uvicorn / systemd
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)

from sqlalchemy import delete, func, inspect, select, text

from app.db import models  # noqa: F401
from app.db.models import (
    ChildUser,
    ContentItem,
    GuideMessage,
    GuideSession,
    ParentChildBind,
    QaMessage,
    QaSession,
    TalentAssessment,
    TalentAssessmentArchive,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
    UserSession,
)
from app.db.session import get_engine, get_session_factory, get_database_url, init_db
from app.services.catalog_import import import_all_xet_catalogs, import_catalog

# 按外键依赖顺序 DELETE（子表在前）
_WIPE_ORDER = (
    GuideMessage,
    GuideSession,
    QaMessage,
    QaSession,
    TrainingRecord,
    TrainingItem,
    TrainingPlan,
    TrainingWindow,
    UserSession,
    ParentChildBind,
    TalentAssessmentArchive,
    TalentAssessment,
    ChildUser,
)


def _confirm_database(url: str) -> None:
    print(f"目标库: {url}")
    if "127.0.0.1" in url or "localhost" in url:
        return
    ans = input("即将操作远程/生产数据库，输入 yes 继续: ").strip().lower()
    if ans != "yes":
        print("已取消")
        sys.exit(1)


def drop_all_tables() -> list[str]:
    engine = get_engine()
    insp = inspect(engine)
    tables = list(insp.get_table_names())
    if not tables:
        return []
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for name in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS `{name}`"))
        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    return tables


def wipe_data(*, include_content: bool = False) -> dict[str, int]:
    session = get_session_factory()()
    counts: dict[str, int] = {}
    try:
        for model in _WIPE_ORDER:
            name = model.__tablename__
            counts[name] = session.scalar(select(func.count()).select_from(model)) or 0
            session.execute(delete(model))

        if include_content:
            counts["content_item"] = session.scalar(select(func.count()).select_from(ContentItem)) or 0
            session.execute(delete(ContentItem))
            session.commit()
            counts["content_item_imported"] = import_catalog(session, replace=False)
        else:
            session.commit()
    finally:
        session.close()
    return counts


def _ensure_admin_and_catalog(*, import_content: bool) -> None:
    from app.services.auth_service import ensure_admin_account

    session = get_session_factory()()
    try:
        admin = ensure_admin_account(session)
        if admin:
            print(f"管理员账号已就绪: login_name={admin.login_name}")

        if import_content:
            session.execute(delete(ContentItem))
            session.commit()
            n = import_catalog(session, replace=False)
            print(f"content_item 重新导入: {n} 条")
        else:
            cnt = session.scalar(select(func.count()).select_from(ContentItem)) or 0
            if cnt == 0:
                added = sum(import_all_xet_catalogs(session).values())
                print(f"音频目录为空，自动导入 {added} 条")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset JNAO database data or rebuild schema")
    parser.add_argument("--all", action="store_true", help="Also wipe and re-import content_item")
    parser.add_argument(
        "--drop-rebuild",
        action="store_true",
        help="DROP all tables and run init_db() (server fresh deploy)",
    )
    parser.add_argument("-y", action="store_true", help="Skip confirmation on non-local DATABASE_URL")
    args = parser.parse_args()

    url = get_database_url()
    if not args.y:
        _confirm_database(url)

    if args.drop_rebuild:
        dropped = drop_all_tables()
        print(f"已删除 {len(dropped)} 张表")
        init_db()
        print("表结构已通过 init_db() + migrate 补丁重建完成")
        _ensure_admin_and_catalog(import_content=args.all)
    else:
        init_db()
        before = wipe_data(include_content=args.all)
        print("已清空业务数据:")
        for table, n in before.items():
            if table != "content_item_imported":
                print(f"  {table}: {n} 条")
        if args.all and "content_item_imported" in before:
            print(f"  content_item 重新导入: {before['content_item_imported']} 条")

    print()
    print("请重启后端服务，并在浏览器清 localStorage:")
    print("  localStorage.clear(); location.reload()")


if __name__ == "__main__":
    main()
