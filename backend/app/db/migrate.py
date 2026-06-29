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
        (
            "training_plan",
            "media_exhausted",
            "ALTER TABLE training_plan ADD COLUMN media_exhausted INTEGER DEFAULT 0",
        ),
        (
            "training_record",
            "train_date",
            "ALTER TABLE training_record ADD COLUMN train_date DATE",
        ),
    ]
    dialect = engine.dialect.name
    for table, column, ddl in patches:
        if column in _column_names(engine, table):
            continue
        stmt = ddl
        if dialect == "mysql":
            if table == "training_record" and column == "train_date":
                stmt = "ALTER TABLE training_record ADD COLUMN train_date DATE NULL AFTER item_id"
            else:
                stmt = ddl.replace(" JSON", " JSON NULL")
        with engine.begin() as conn:
            conn.execute(text(stmt))

    if "train_date" in _column_names(engine, "training_record"):
        with engine.begin() as conn:
            if dialect == "mysql":
                conn.execute(
                    text(
                        """
                        UPDATE training_record r
                        INNER JOIN training_plan p ON r.plan_id = p.id
                        SET r.train_date = p.plan_date
                        WHERE r.train_date IS NULL AND p.plan_date IS NOT NULL
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE training_record
                        SET train_date = DATE(created_at)
                        WHERE train_date IS NULL AND created_at IS NOT NULL
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        UPDATE training_record
                        SET train_date = (
                            SELECT p.plan_date FROM training_plan p
                            WHERE p.id = training_record.plan_id
                        )
                        WHERE train_date IS NULL AND plan_id IS NOT NULL
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        UPDATE training_record
                        SET train_date = date(created_at)
                        WHERE train_date IS NULL AND created_at IS NOT NULL
                        """
                    )
                )
