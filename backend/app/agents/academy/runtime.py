"""学院智能体运行时。会话走 Checkpointer，长期感知走 Store。

测试和 sqlite 内存库用 InMemorySaver。MySQL 用 langgraph-checkpoint-mysql
的 AIOMySQLSaver，thread_id 不要改。这一版不接 Redis、Celery。
"""

from __future__ import annotations

import asyncio
import logging
import sys

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

log = logging.getLogger(__name__)

_SAVER = None
_STORE = InMemoryStore()
_CONN = None
_GENERATION = 0
_LOCK: asyncio.Lock | None = None


def _database_url() -> str:
    try:
        from config.loader import load_settings

        return str((load_settings().get("database") or {}).get("url") or "")
    except Exception:
        return ""


def _use_memory() -> bool:
    if "pytest" in sys.modules:
        return True
    url = _database_url()
    return (not url.startswith("mysql")) or (":memory:" in url)


def _mysql_uri(url: str) -> str:
    for prefix in ("mysql+pymysql://", "mysql+mysqldb://", "mysql+aiomysql://"):
        if url.startswith(prefix):
            return "mysql://" + url[len(prefix):]
    return url


def _drop_bots() -> None:
    try:
        from app.agents.academy import graph as academy_graph

        academy_graph._BOTS.clear()
    except Exception:
        pass


def reset_checkpointer() -> None:
    """连接坏掉或 event loop 重建后，丢掉旧 saver / 已编译图。"""
    global _SAVER, _CONN, _GENERATION
    conn = _CONN
    _SAVER = None
    _CONN = None
    _GENERATION += 1
    _drop_bots()
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def checkpointer():
    """同步取检查点。未就绪时用内存，禁止抛错打断发言。"""
    global _SAVER, _GENERATION
    if _SAVER is None:
        _SAVER = InMemorySaver()
        _GENERATION += 1
        log.warning("学院检查点尚未异步就绪，本轮用内存")
    return _SAVER


def memory_store():
    return _STORE


def checkpointer_generation() -> int:
    return _GENERATION


def _lock() -> asyncio.Lock:
    global _LOCK
    if _LOCK is None:
        _LOCK = asyncio.Lock()
    return _LOCK


async def ensure_checkpointer():
    """第一次开口前建好检查点。图编译会用到它，必须先于 bot_graph。"""
    global _SAVER, _CONN, _GENERATION
    async with _lock():
        if _SAVER is not None and not isinstance(_SAVER, InMemorySaver):
            return _SAVER
        if _use_memory():
            if _SAVER is None:
                _SAVER = InMemorySaver()
                _GENERATION += 1
            return _SAVER
        try:
            import aiomysql
            from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

            info = AIOMySQLSaver.parse_conn_string(_mysql_uri(_database_url()))
            conn = await aiomysql.connect(
                host=info.get("host") or "127.0.0.1",
                user=info.get("user"),
                password=info.get("password") or "",
                db=info.get("db"),
                port=info.get("port") or 3306,
                unix_socket=info.get("unix_socket"),
                charset="utf8mb4",
                autocommit=True,
            )
            saver = AIOMySQLSaver(conn)
            await saver.setup()
            old = _CONN
            _CONN = conn
            _SAVER = saver
            _GENERATION += 1
            _drop_bots()
            if old is not None and old is not conn:
                try:
                    old.close()
                except Exception:
                    pass
        except Exception:
            log.exception("MySQL 检查点不可用，这一轮退回内存，重启后私有记忆不会留下")
            if _SAVER is None:
                _SAVER = InMemorySaver()
                _GENERATION += 1
                _drop_bots()
        return _SAVER


def thread_id(child_user_id: int | None, episode_id: str, character_key: str) -> str:
    episode = (episode_id or "E13").strip().upper()
    return f"academy:{int(child_user_id or 0)}:{episode}:{character_key}"


def put_canon(
    bot_id: str,
    kind: str,
    text: str,
    episode_id: str | None,
    revision: int,
) -> None:
    """配置更新写入这个 Bot 的长期记忆。不写进别人的命名空间。"""
    body = " ".join((text or "").split())
    if not body:
        return
    memory_store().put(
        (bot_id, "canon"),
        f"{kind}:{episode_id or 'self'}:{int(revision)}",
        {"kind": kind, "episode_id": episode_id, "text": body[:200], "revision": int(revision)},
    )
