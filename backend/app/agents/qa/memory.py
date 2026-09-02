"""QA Agent 记忆层 — 会话消息 + 会话内滚动摘要（删会话即清空）。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import QaMessage, QaSession

from app.agents.memory_policy import (
    MAX_DIGEST_CHARS,
    HISTORY_KEEP_DEFAULT,
    HISTORY_LOAD_DEFAULT,
    fold_overflow_history as _fold_overflow_history,
    digest_prompt_block,
)

MEMORY_VERSION = 1


def _empty_memory() -> dict[str, Any]:
    return {
        "version": MEMORY_VERSION,
        "updated_at": None,
        "rolling_summary": "",
    }


def load_session_memory(session: QaSession | None) -> dict[str, Any]:
    mem = _empty_memory()
    if not session or not isinstance(session.meta_json, dict):
        return mem
    raw = session.meta_json
    mem["rolling_summary"] = str(raw.get("rolling_summary") or "")[:MAX_DIGEST_CHARS]
    mem["updated_at"] = raw.get("updated_at")
    mem["version"] = int(raw.get("version") or MEMORY_VERSION)
    return mem


def save_session_memory(db: Session, session: QaSession, mem: dict[str, Any]) -> None:
    """写入会话 meta；由调用方统一 commit（删会话即清空摘要）。"""
    del db  # 保持签名与 Guide 侧一致，便于测试注入
    session.meta_json = {
        "version": MEMORY_VERSION,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "rolling_summary": str(mem.get("rolling_summary") or "")[:MAX_DIGEST_CHARS],
    }
    flag_modified(session, "meta_json")


def fold_overflow_history(
    messages: list[dict],
    mem: dict[str, Any],
    *,
    keep: int = HISTORY_KEEP_DEFAULT,
) -> tuple[list[dict], dict[str, Any]]:
    return _fold_overflow_history(
        messages,
        mem,
        keep=keep,
        max_digest_chars=MAX_DIGEST_CHARS,
        empty_mem_factory=_empty_memory,
    )


def memory_to_prompt_block(mem: dict[str, Any] | None) -> str:
    return digest_prompt_block(mem, label="近期本题对话摘要")


class QaMemory:
    """学科答疑对话记忆：以 qa_session / qa_message 为持久化存储。"""

    @staticmethod
    def load_chat_history(
        session: QaSession,
        *,
        limit: int = HISTORY_KEEP_DEFAULT,
        roles: tuple[str, ...] = ("user", "assistant"),
    ) -> list[dict]:
        msgs = [m for m in session.messages if m.role in roles]
        if limit and limit > 0:
            msgs = msgs[-limit:]
        return [{"role": m.role, "content": m.content} for m in msgs]

    @staticmethod
    def prepare_history_and_digest(
        db: Session,
        session: QaSession,
        *,
        load_limit: int = HISTORY_LOAD_DEFAULT,
        keep: int = HISTORY_KEEP_DEFAULT,
    ) -> tuple[list[dict], str]:
        """生成前：加载历史 → 折叠溢出进会话摘要 → 有变化则落库。

        写入时机见 memory_policy 模块说明；助手回复只写入 QaMessage，
        不在此回写 rolling_summary。
        """
        full = QaMemory.load_chat_history(session, limit=load_limit)
        mem = load_session_memory(session)
        history, mem = fold_overflow_history(full, mem, keep=keep)
        if str(mem.get("rolling_summary") or "") != str(
            (session.meta_json or {}).get("rolling_summary") or ""
        ):
            save_session_memory(db, session, mem)
        return history, memory_to_prompt_block(mem)

    @staticmethod
    def load_messages(db: Session, session_id: int, child_user_id: int) -> list[dict] | None:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            return None
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "image_url": m.image_url,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in session.messages
        ]

    @staticmethod
    def recent_topics(db: Session, child_user_id: int, limit: int = 5) -> list[str]:
        rows = db.scalars(
            select(QaSession)
            .where(QaSession.child_user_id == child_user_id)
            .order_by(QaSession.id.desc())
            .limit(limit)
        ).all()
        return [r.title for r in rows if r.title and r.title != "新对话"]

    @staticmethod
    def append_message(
        db: Session,
        *,
        session_id: int,
        role: str,
        content: str,
        image_url: str | None = None,
        meta_json: dict | None = None,
    ) -> QaMessage:
        row = QaMessage(
            session_id=session_id,
            role=role,
            content=content,
            image_url=image_url,
            meta_json=meta_json,
        )
        db.add(row)
        return row
