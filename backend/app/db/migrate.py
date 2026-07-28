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
            "training_plan",
            "plan_customized",
            "ALTER TABLE training_plan ADD COLUMN plan_customized INTEGER DEFAULT 0",
        ),
        (
            "child_user",
            "account_status",
            "ALTER TABLE child_user ADD COLUMN account_status VARCHAR(20) DEFAULT 'active'",
        ),
        (
            "child_user",
            "deleted_at",
            "ALTER TABLE child_user ADD COLUMN deleted_at DATETIME",
        ),
        (
            "training_record",
            "train_date",
            "ALTER TABLE training_record ADD COLUMN train_date DATE",
        ),
        (
            "daka_member",
            "wechat_bound_at",
            "ALTER TABLE daka_member ADD COLUMN wechat_bound_at DATETIME",
        ),
        (
            "daka_member",
            "company_verified_at",
            "ALTER TABLE daka_member ADD COLUMN company_verified_at DATETIME",
        ),
        (
            "guide_message",
            "meta_json",
            "ALTER TABLE guide_message ADD COLUMN meta_json JSON",
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
    _apply_user_session_table(engine)
    _apply_wechat_auth_tables(engine)
    _apply_daka_member_table(engine)
    _backfill_daka_member_gate(engine)
    _apply_parent_child_unique_child(engine)
    _migrate_user_session_utc_to_cst(engine)


def _apply_parent_child_unique_child(engine: Engine) -> None:
    """一个孩子只能绑定一个家长 — 去重后加 UNIQUE(child_id)"""
    insp = inspect(engine)
    if "parent_child_bind" not in insp.get_table_names():
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_data_patch (
                    name VARCHAR(64) PRIMARY KEY
                )
                """
            )
        )
        done = conn.execute(
            text("SELECT 1 FROM schema_data_patch WHERE name = 'parent_child_bind_unique_child'")
        ).fetchone()
        if done:
            return
        if dialect == "mysql":
            conn.execute(
                text(
                    """
                    DELETE pcb1 FROM parent_child_bind pcb1
                    INNER JOIN parent_child_bind pcb2
                      ON pcb1.child_id = pcb2.child_id AND pcb1.id > pcb2.id
                    """
                )
            )
            idx = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                      AND table_name = 'parent_child_bind'
                      AND index_name = 'uk_parent_child_child_id'
                    LIMIT 1
                    """
                )
            ).fetchone()
            if not idx:
                conn.execute(
                    text(
                        "ALTER TABLE parent_child_bind "
                        "ADD UNIQUE KEY uk_parent_child_child_id (child_id)"
                    )
                )
        else:
            conn.execute(
                text(
                    """
                    DELETE FROM parent_child_bind
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM parent_child_bind GROUP BY child_id
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uk_parent_child_child_id "
                    "ON parent_child_bind(child_id)"
                )
            )
        conn.execute(
            text(
                "INSERT INTO schema_data_patch (name) VALUES ('parent_child_bind_unique_child')"
            )
        )


def _migrate_user_session_utc_to_cst(engine: Engine) -> None:
    """历史会话时间曾为 UTC naive，统一转为北京时间 naive（仅执行一次）"""
    insp = inspect(engine)
    if "user_session" not in insp.get_table_names():
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_data_patch (
                    name VARCHAR(64) PRIMARY KEY
                )
                """
            )
        )
        done = conn.execute(
            text("SELECT 1 FROM schema_data_patch WHERE name = 'user_session_utc_to_cst'")
        ).fetchone()
        if done:
            return
        if dialect == "mysql":
            conn.execute(
                text(
                    """
                    UPDATE user_session
                    SET last_active_at = DATE_ADD(last_active_at, INTERVAL 8 HOUR),
                        created_at = DATE_ADD(created_at, INTERVAL 8 HOUR)
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE user_session
                    SET last_active_at = datetime(last_active_at, '+8 hours'),
                        created_at = datetime(created_at, '+8 hours')
                    """
                )
            )
        conn.execute(
            text("INSERT INTO schema_data_patch (name) VALUES ('user_session_utc_to_cst')")
        )


def _apply_wechat_auth_tables(engine: Engine) -> None:
    insp = inspect(engine)
    dialect = engine.dialect.name
    if "wx_member_snapshot" not in insp.get_table_names():
        if dialect == "mysql":
            ddl = """
                CREATE TABLE wx_member_snapshot (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    wx_member_id INT NULL,
                    openid VARCHAR(64) NOT NULL,
                    unionid VARCHAR(64) NULL,
                    mobile VARCHAR(20) NULL,
                    nickname VARCHAR(255) NULL,
                    truename VARCHAR(64) NULL,
                    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_wx_snapshot_openid (openid),
                    KEY idx_wx_snapshot_mobile (mobile),
                    KEY idx_wx_snapshot_unionid (unionid)
                )
            """
        else:
            ddl = """
                CREATE TABLE wx_member_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wx_member_id INTEGER,
                    openid VARCHAR(64) NOT NULL UNIQUE,
                    unionid VARCHAR(64),
                    mobile VARCHAR(20),
                    nickname VARCHAR(255),
                    truename VARCHAR(64),
                    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
        with engine.begin() as conn:
            conn.execute(text(ddl))

    if "parent_wechat_bind" not in insp.get_table_names():
        if dialect == "mysql":
            ddl = """
                CREATE TABLE parent_wechat_bind (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    parent_id INT NOT NULL,
                    openid VARCHAR(64) NOT NULL,
                    unionid VARCHAR(64) NULL,
                    wx_member_id INT NULL,
                    app_id VARCHAR(32) NOT NULL,
                    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME NULL,
                    UNIQUE KEY uk_wechat_openid_app (openid, app_id),
                    UNIQUE KEY uk_wechat_parent_app (parent_id, app_id),
                    KEY idx_wechat_unionid (unionid),
                    FOREIGN KEY (parent_id) REFERENCES child_user(id)
                )
            """
        else:
            ddl = """
                CREATE TABLE parent_wechat_bind (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER NOT NULL,
                    openid VARCHAR(64) NOT NULL,
                    unionid VARCHAR(64),
                    wx_member_id INTEGER,
                    app_id VARCHAR(32) NOT NULL,
                    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME,
                    UNIQUE (openid, app_id),
                    UNIQUE (parent_id, app_id),
                    FOREIGN KEY (parent_id) REFERENCES child_user(id)
                )
            """
        with engine.begin() as conn:
            conn.execute(text(ddl))


def _apply_daka_member_table(engine: Engine) -> None:
    insp = inspect(engine)
    if "daka_member" in insp.get_table_names():
        return
    dialect = engine.dialect.name
    if dialect == "mysql":
        ddl = """
            CREATE TABLE daka_member (
                id INT PRIMARY KEY AUTO_INCREMENT,
                parent_id INT NOT NULL,
                mobile VARCHAR(20) NOT NULL,
                openid VARCHAR(64) NULL,
                unionid VARCHAR(64) NULL,
                register_channel VARCHAR(20) NOT NULL,
                legacy_matched TINYINT NOT NULL DEFAULT 0,
                legacy_wx_member_id INT NULL,
                real_name VARCHAR(64) NULL,
                nickname VARCHAR(50) NULL,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_daka_member_parent (parent_id),
                UNIQUE KEY uk_daka_member_mobile (mobile),
                UNIQUE KEY uk_daka_member_openid (openid),
                KEY idx_daka_member_legacy_wx (legacy_wx_member_id),
                FOREIGN KEY (parent_id) REFERENCES child_user(id)
            )
        """
    else:
        ddl = """
            CREATE TABLE daka_member (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NOT NULL UNIQUE,
                mobile VARCHAR(20) NOT NULL UNIQUE,
                openid VARCHAR(64) UNIQUE,
                unionid VARCHAR(64),
                register_channel VARCHAR(20) NOT NULL,
                legacy_matched INTEGER NOT NULL DEFAULT 0,
                legacy_wx_member_id INTEGER,
                real_name VARCHAR(64),
                nickname VARCHAR(50),
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES child_user(id)
            )
        """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _backfill_daka_member_gate(engine: Engine) -> None:
    if "wechat_bound_at" not in _column_names(engine, "daka_member"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE daka_member
                SET wechat_bound_at = COALESCE(wechat_bound_at, updated_at),
                    company_verified_at = COALESCE(company_verified_at, updated_at)
                WHERE openid IS NOT NULL AND openid != ''
                  AND wechat_bound_at IS NULL
                """
            )
        )


def _apply_user_session_table(engine: Engine) -> None:
    insp = inspect(engine)
    if "user_session" in insp.get_table_names():
        return
    dialect = engine.dialect.name
    if dialect == "mysql":
        ddl = """
            CREATE TABLE user_session (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                session_token VARCHAR(64) NOT NULL UNIQUE,
                device_label VARCHAR(100) NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES child_user(id)
            )
        """
    else:
        ddl = """
            CREATE TABLE user_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token VARCHAR(64) NOT NULL UNIQUE,
                device_label VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES child_user(id)
            )
        """
    with engine.begin() as conn:
        conn.execute(text(ddl))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_session_user ON user_session(user_id)"))


def _apply_parent_auth_patches(engine: Engine) -> None:
    """家长/孩子账号：列 + parent_child_bind 表"""
    dialect = engine.dialect.name
    child_cols = _column_names(engine, "child_user")

    col_ddls: list[tuple[str, str]] = [
        ("password_hash", "ALTER TABLE child_user ADD COLUMN password_hash VARCHAR(128)"),
        ("role", "ALTER TABLE child_user ADD COLUMN role VARCHAR(10) DEFAULT 'student'"),
        ("login_name", "ALTER TABLE child_user ADD COLUMN login_name VARCHAR(50)"),
        ("child_quota", "ALTER TABLE child_user ADD COLUMN child_quota INTEGER"),
        ("session_token", "ALTER TABLE child_user ADD COLUMN session_token VARCHAR(64)"),
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

    # 单设备登录：为现有用户补充 session_token
    if "session_token" in _column_names(engine, "child_user"):
        with engine.begin() as conn:
            if dialect == "sqlite":
                # SQLite 不支持 uuid，用随机 hex 字符串
                conn.execute(
                    text(
                        "UPDATE child_user SET session_token = hex(randomblob(32)) "
                        "WHERE session_token IS NULL"
                    )
                )
            else:
                conn.execute(
                    text(
                        "UPDATE child_user SET session_token = REPLACE(UUID(), '-', '') "
                        "WHERE session_token IS NULL"
                    )
                )

    if dialect == "sqlite":
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uk_child_user_login_name "
                    "ON child_user(login_name) WHERE login_name IS NOT NULL"
                )
            )
