"""QA / Guide 历史会话归档 — 超期会话写入 archive 表后从主表删除。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    GuideMessage,
    GuideSession,
    GuideSessionArchive,
    QaMessage,
    QaSession,
    QaSessionArchive,
)
from app.services.qa_cache import invalidate_session_list


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def qa_session_snapshot(session: QaSession) -> dict[str, Any]:
    return {
        "session": {
            "id": session.id,
            "child_user_id": session.child_user_id,
            "title": session.title,
            "subject": session.subject,
            "meta_json": session.meta_json,
            "created_at": _iso(session.created_at),
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "voice_url": m.voice_url,
                "image_url": m.image_url,
                "meta_json": m.meta_json,
                "created_at": _iso(m.created_at),
            }
            for m in (session.messages or [])
        ],
    }


def guide_session_snapshot(session: GuideSession) -> dict[str, Any]:
    return {
        "session": {
            "id": session.id,
            "child_user_id": session.child_user_id,
            "title": session.title,
            "created_at": _iso(session.created_at),
            "updated_at": _iso(session.updated_at),
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "meta_json": m.meta_json,
                "created_at": _iso(m.created_at),
            }
            for m in (session.messages or [])
        ],
    }


def _user_message_count(snapshot: dict | None) -> int:
    if not snapshot:
        return 0
    msgs = snapshot.get("messages") or []
    return sum(1 for m in msgs if m.get("role") == "user")


def count_archived_qa_user_messages(db: Session, child_user_id: int) -> int:
    rows = db.scalars(
        select(QaSessionArchive).where(QaSessionArchive.child_user_id == child_user_id)
    ).all()
    return sum(_user_message_count(r.snapshot_json) for r in rows)


def earliest_archived_qa_created_at(db: Session, child_user_id: int) -> datetime | None:
    earliest: datetime | None = None
    rows = db.scalars(
        select(QaSessionArchive).where(QaSessionArchive.child_user_id == child_user_id)
    ).all()
    for row in rows:
        raw = ((row.snapshot_json or {}).get("session") or {}).get("created_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw))
        except ValueError:
            continue
        if earliest is None or dt < earliest:
            earliest = dt
    return earliest


def earliest_qa_created_at(db: Session, child_user_id: int) -> datetime | None:
    live = db.scalar(
        select(QaSession)
        .where(QaSession.child_user_id == child_user_id)
        .order_by(QaSession.id.asc())
        .limit(1)
    )
    live_dt = live.created_at if live and live.created_at else None
    archived_dt = earliest_archived_qa_created_at(db, child_user_id)
    if live_dt and archived_dt:
        return min(live_dt, archived_dt)
    return live_dt or archived_dt


def _ranked_qa_ids(
    db: Session,
    *,
    cutoff: datetime,
    keep_recent: int,
    batch_size: int,
) -> list[int]:
    ranked = (
        select(
            QaSession.id.label("session_id"),
            func.row_number()
            .over(
                partition_by=QaSession.child_user_id,
                order_by=QaSession.id.desc(),
            )
            .label("rn"),
            QaSession.created_at,
        )
    ).subquery()
    return list(
        db.scalars(
            select(ranked.c.session_id)
            .where(
                ranked.c.rn > keep_recent,
                ranked.c.created_at < cutoff,
            )
            .order_by(ranked.c.session_id.asc())
            .limit(batch_size)
        ).all()
    )


def _ranked_guide_ids(
    db: Session,
    *,
    cutoff: datetime,
    keep_recent: int,
    batch_size: int,
) -> list[int]:
    activity = func.coalesce(GuideSession.updated_at, GuideSession.created_at)
    ranked = (
        select(
            GuideSession.id.label("session_id"),
            func.row_number()
            .over(
                partition_by=GuideSession.child_user_id,
                order_by=(GuideSession.updated_at.desc(), GuideSession.id.desc()),
            )
            .label("rn"),
            activity.label("activity_at"),
        )
    ).subquery()
    return list(
        db.scalars(
            select(ranked.c.session_id)
            .where(
                ranked.c.rn > keep_recent,
                ranked.c.activity_at < cutoff,
            )
            .order_by(ranked.c.session_id.asc())
            .limit(batch_size)
        ).all()
    )


def archive_qa_sessions(
    db: Session,
    *,
    retain_days: int = 180,
    keep_recent: int = 20,
    batch_size: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    retain_days = max(1, retain_days)
    keep_recent = max(0, keep_recent)
    batch_size = max(1, batch_size)
    cutoff = datetime.now() - timedelta(days=retain_days)

    session_ids = _ranked_qa_ids(
        db, cutoff=cutoff, keep_recent=keep_recent, batch_size=batch_size
    )
    if not session_ids:
        return {
            "kind": "qa",
            "sessions": 0,
            "messages": 0,
            "affected_children": 0,
            "dry_run": dry_run,
            "retain_days": retain_days,
            "keep_recent": keep_recent,
        }

    sessions = db.scalars(
        select(QaSession)
        .options(joinedload(QaSession.messages))
        .where(QaSession.id.in_(session_ids))
    ).unique().all()

    message_count = sum(len(s.messages or []) for s in sessions)
    child_ids = {s.child_user_id for s in sessions}

    if dry_run:
        return {
            "kind": "qa",
            "sessions": len(sessions),
            "messages": message_count,
            "affected_children": len(child_ids),
            "dry_run": True,
            "retain_days": retain_days,
            "keep_recent": keep_recent,
            "session_ids": session_ids[:20],
        }

    for session in sessions:
        db.add(
            QaSessionArchive(
                original_session_id=session.id,
                child_user_id=session.child_user_id,
                snapshot_json=qa_session_snapshot(session),
            )
        )
    db.execute(delete(QaMessage).where(QaMessage.session_id.in_(session_ids)))
    db.execute(delete(QaSession).where(QaSession.id.in_(session_ids)))
    db.commit()

    for child_id in child_ids:
        invalidate_session_list(child_id)

    return {
        "kind": "qa",
        "sessions": len(sessions),
        "messages": message_count,
        "affected_children": len(child_ids),
        "dry_run": False,
        "retain_days": retain_days,
        "keep_recent": keep_recent,
    }


def archive_guide_sessions(
    db: Session,
    *,
    retain_days: int = 180,
    keep_recent: int = 10,
    batch_size: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    retain_days = max(1, retain_days)
    keep_recent = max(0, keep_recent)
    batch_size = max(1, batch_size)
    cutoff = datetime.now() - timedelta(days=retain_days)

    session_ids = _ranked_guide_ids(
        db, cutoff=cutoff, keep_recent=keep_recent, batch_size=batch_size
    )
    if not session_ids:
        return {
            "kind": "guide",
            "sessions": 0,
            "messages": 0,
            "affected_children": 0,
            "dry_run": dry_run,
            "retain_days": retain_days,
            "keep_recent": keep_recent,
        }

    sessions = db.scalars(
        select(GuideSession)
        .options(joinedload(GuideSession.messages))
        .where(GuideSession.id.in_(session_ids))
    ).unique().all()

    message_count = sum(len(s.messages or []) for s in sessions)
    child_ids = {s.child_user_id for s in sessions}

    if dry_run:
        return {
            "kind": "guide",
            "sessions": len(sessions),
            "messages": message_count,
            "affected_children": len(child_ids),
            "dry_run": True,
            "retain_days": retain_days,
            "keep_recent": keep_recent,
            "session_ids": session_ids[:20],
        }

    for session in sessions:
        db.add(
            GuideSessionArchive(
                original_session_id=session.id,
                child_user_id=session.child_user_id,
                snapshot_json=guide_session_snapshot(session),
            )
        )
    db.execute(delete(GuideMessage).where(GuideMessage.session_id.in_(session_ids)))
    db.execute(delete(GuideSession).where(GuideSession.id.in_(session_ids)))
    db.commit()

    return {
        "kind": "guide",
        "sessions": len(sessions),
        "messages": message_count,
        "affected_children": len(child_ids),
        "dry_run": False,
        "retain_days": retain_days,
        "keep_recent": keep_recent,
    }


def run_chat_archive(
    db: Session,
    *,
    retain_days: int = 180,
    qa_keep_recent: int = 20,
    guide_keep_recent: int = 10,
    batch_size: int = 100,
    dry_run: bool = False,
    include_qa: bool = True,
    include_guide: bool = True,
) -> dict[str, Any]:
    qa_result = (
        archive_qa_sessions(
            db,
            retain_days=retain_days,
            keep_recent=qa_keep_recent,
            batch_size=batch_size,
            dry_run=dry_run,
        )
        if include_qa
        else {"kind": "qa", "sessions": 0, "messages": 0, "skipped": True}
    )
    guide_result = (
        archive_guide_sessions(
            db,
            retain_days=retain_days,
            keep_recent=guide_keep_recent,
            batch_size=batch_size,
            dry_run=dry_run,
        )
        if include_guide
        else {"kind": "guide", "sessions": 0, "messages": 0, "skipped": True}
    )
    return {
        "ok": True,
        "dry_run": dry_run,
        "retain_days": retain_days,
        "qa": qa_result,
        "guide": guide_result,
    }
