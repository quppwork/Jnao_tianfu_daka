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

    _apply_parent_auth_patches(engine)


def _apply_parent_auth_patches(engine: Engine) -> None:
    """家长/孩子账号：列 + parent_child_bind 表"""
    dialect = engine.dialect.name
    child_cols = _column_names(engine, "child_user")

    col_ddls: list[tuple[str, str]] = [
        ("password_hash", "ALTER TABLE child_user ADD COLUMN password_hash VARCHAR(128)"),
        ("role", "ALTER TABLE child_user ADD COLUMN role VARCHAR(10) DEFAULT 'student'"),
        ("login_name", "ALTER TABLE child_user ADD COLUMN login_name VARCHAR(50)"),
        ("child_quota", "ALTER TABLE child_user ADD COLUMN child_quota INTEGER"),
    ]
    for column, ddl in col_ddls:
        if column in child_cols:
            continue
        stmt = ddl
        if dialect == "mysql" and "JSON" not in ddl:
            stmt = ddl.replace(" INTEGER", " INT NULL")
        with engine.begin() as conn:
            conn.execute(text(stmt))

    insp = inspect(engine)
    if "parent_child_bind" not in insp.get_table_names():
        if dialect == "mysql":
            ddl = """
                CREATE TABLE parent_child_bind (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    parent_id INT NOT NULL,
                    child_id INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_parent_child (parent_id, child_id),
                    FOREIGN KEY (parent_id) REFERENCES child_user(id),
                    FOREIGN KEY (child_id) REFERENCES child_user(id)
                )
            """
        else:
            ddl = """
                CREATE TABLE parent_child_bind (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER NOT NULL,
                    child_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (parent_id, child_id),
                    FOREIGN KEY (parent_id) REFERENCES child_user(id),
                    FOREIGN KEY (child_id) REFERENCES child_user(id)
                )
            """
        with engine.begin() as conn:
            conn.execute(text(ddl))

    if dialect == "sqlite":
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uk_child_user_login_name "
                    "ON child_user(login_name) WHERE login_name IS NOT NULL"
                )
            )
