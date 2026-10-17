"""报告天赋解答会话 — assessment_id 为 thread_key；owner = child_user_id。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ReportTalentMessage, TalentAssessment
from app.memory.protocols import ThreadMessage, ThreadRef


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _to_msg(row: ReportTalentMessage) -> ThreadMessage:
    return ThreadMessage(
        id=int(row.id),
        role=str(row.role or ""),
        content=str(row.content or ""),
        created_at=_iso(row.created_at),
        meta={"retrieved": int(row.retrieved or 0)},
    )


class ReportTalentThreadAdapter:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _assessment_id(self, ref: ThreadRef) -> int:
        try:
            return int(ref.thread_key)
        except (TypeError, ValueError) as exc:
            raise ValueError("report_talent.thread_key 须为 assessment_id") from exc

    def _assert_owner(self, assessment_id: int, owner_user_id: int) -> TalentAssessment:
        row = self._db.get(TalentAssessment, assessment_id)
        if not row or int(row.child_user_id) != int(owner_user_id):
            raise PermissionError("报告不存在或无权访问会话")
        return row

    def list_messages(self, ref: ThreadRef, *, limit: int = 100) -> list[ThreadMessage]:
        aid = self._assessment_id(ref)
        self._assert_owner(aid, ref.owner_user_id)
        lim = max(1, min(int(limit or 100), 500))
        rows = list(
            self._db.scalars(
                select(ReportTalentMessage)
                .where(
                    ReportTalentMessage.assessment_id == aid,
                    ReportTalentMessage.child_user_id == int(ref.owner_user_id),
                )
                .order_by(ReportTalentMessage.id.asc())
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
        aid = self._assessment_id(ref)
        self._assert_owner(aid, ref.owner_user_id)
        retrieved = int((meta or {}).get("retrieved") or 0)
        row = ReportTalentMessage(
            assessment_id=aid,
            child_user_id=int(ref.owner_user_id),
            role=str(role or "").strip() or "user",
            content=str(content or ""),
            retrieved=retrieved,
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
        aid = self._assessment_id(ref)
        self._assert_owner(aid, ref.owner_user_id)
        result = self._db.execute(
            delete(ReportTalentMessage).where(
                ReportTalentMessage.assessment_id == aid,
                ReportTalentMessage.child_user_id == int(ref.owner_user_id),
            )
        )
        if commit:
            self._db.commit()
        return int(result.rowcount or 0)
