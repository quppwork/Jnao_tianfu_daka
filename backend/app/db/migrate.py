"""轻量 schema 补丁 — create_all 不会给已有表加列，此处补齐"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(engine: Engine, table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def apply_schema_patches(engine: Engine) -> None:
    """幂等执行 migrations/ 中需在线追加的列"""
    patches: list[tuple[str, str, str]] = [
        (
            "training_item",
            "watch_progress",
            "ALTER TABLE training_item ADD COLUMN watch_progress JSON",
        ),
    ]
    dialect = engine.dialect.name
    for table, column, ddl in patches:
        if column in _column_names(engine, table):
            continue
        stmt = ddl
        if dialect == "mysql":
            stmt = ddl.replace(" JSON", " JSON NULL")
        with engine.begin() as conn:
            conn.execute(text(stmt))
