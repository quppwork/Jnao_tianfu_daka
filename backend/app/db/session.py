"""数据库引擎与会话管理"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.loader import load_settings
from app.db.base import Base
from app.db import models  # noqa: F401 — register models

_engine = None
_SessionLocal = None


def _sqlite_path(url: str) -> None:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        db_path = url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def get_database_url() -> str:
    return load_settings()["database"]["url"]


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = get_database_url()
        _sqlite_path(url)
        if url.startswith("sqlite"):
            _engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )

            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, _):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session_factory():
    get_engine()
    return _SessionLocal


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    from app.db.migrate import apply_schema_patches

    apply_schema_patches(engine)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
