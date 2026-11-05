"""学科答疑会话 — thread_key = qa_session.id；owner = child_user_id。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import QaMessage, QaSession
from app.memory.protocols import ThreadMessage, ThreadRef


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _to_msg(row: QaMessage) -> ThreadMessage:
    meta: dict[str, Any] = {}
    if isinstance(row.meta_json, dict):
        meta.update(row.meta_json)
    if row.image_url:
        meta["image_url"] = row.image_url
    if row.voice_url:
        meta["voice_url"] = row.voice_url
    return ThreadMessage(
        id=int(row.id),
        role=str(row.role or ""),
        content=str(row.content or ""),
        created_at=_iso(row.created_at),
        meta=meta,
    )


class QaThreadAdapter:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _session_id(self, ref: ThreadRef) -> int:
        try:
            return int(ref.thread_key)
        except (TypeError, ValueError) as exc:
            raise ValueError("qa.thread_key 须为 session_id") from exc

    def _assert_owner(self, session_id: int, owner_user_id: int) -> QaSession:
        row = self._db.get(QaSession, session_id)
        if not row or int(row.child_user_id) != int(owner_user_id):
            raise PermissionError("答疑会话不存在或无权访问")
        return row

    def list_messages(self, ref: ThreadRef, *, limit: int = 100) -> list[ThreadMessage]:
        sid = self._session_id(ref)
        self._assert_owner(sid, ref.owner_user_id)
        lim = max(1, min(int(limit or 100), 500))
        rows = list(
            self._db.scalars(
                select(QaMessage)
                .where(QaMessage.session_id == sid)
                .order_by(QaMessage.id.asc())
                .limit(lim)
            ).all()
        )
        return [_to_msg(r) for r in rows]

    def append(
        self,
        ref: ThreadRef,
        *,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ThreadMessage:
        sid = self._session_id(ref)
        self._assert_owner(sid, ref.owner_user_id)
        meta = dict(meta or {})
        image_url = meta.pop("image_url", None)
        voice_url = meta.pop("voice_url", None)
        row = QaMessage(
            session_id=sid,
            role=str(role or "").strip() or "user",
            content=str(content or ""),
            image_url=str(image_url) if image_url else None,
            voice_url=str(voice_url) if voice_url else None,
            meta_json=meta or None,
        )
        self._db.add(row)
        self._db.flush()
        if commit:
            self._db.commit()
            self._db.refresh(row)
        return _to_msg(row)

    def append_pair(
        self,
        ref: ThreadRef,
        *,
        user_content: str,
        assistant_content: str,
        user_meta: dict[str, Any] | None = None,
        assistant_meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> tuple[ThreadMessage, ThreadMessage]:
        u = self.append(
            ref, role="user", content=user_content, meta=user_meta, commit=False
        )
        a = self.append(
            ref,
            role="assistant",
            content=assistant_content,
            meta=assistant_meta,
            commit=False,
        )
        if commit:
            self._db.commit()
        return u, a

    def clear(self, ref: ThreadRef, *, commit: bool = True) -> int:
        sid = self._session_id(ref)
        self._assert_owner(sid, ref.owner_user_id)
        result = self._db.execute(delete(QaMessage).where(QaMessage.session_id == sid))
        if commit:
            self._db.commit()
        return int(result.rowcount or 0)
