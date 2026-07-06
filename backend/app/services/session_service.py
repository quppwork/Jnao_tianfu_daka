"""多端登录会话管理"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, UserSession
from app.services import auth_service
from app.services.platform_config import max_devices_for_role
from app.services.datetime_fmt import format_cst
from app.services.training_day import TZ


def _now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def _generate_token() -> str:
    return auth_service._generate_session_token()


def list_user_sessions(db: Session, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.last_active_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "device_label": r.device_label,
            "created_at": format_cst(r.created_at),
            "last_active_at": format_cst(r.last_active_at),
        }
        for r in rows
    ]


def revoke_all_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    user = db.get(ChildUser, user_id)
    if user:
        user.session_token = None


def _trim_sessions(db: Session, user: ChildUser) -> None:
    limit = max_devices_for_role(db, user.role or auth_service.ROLE_STUDENT)
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.last_active_at.asc())
    ).all()
    while len(rows) >= limit:
        oldest = rows.pop(0)
        db.delete(oldest)
    db.flush()


def issue_session(db: Session, user: ChildUser, *, device_label: str | None = None) -> str:
    """签发新会话，超出上限时踢掉最久未活跃的设备"""
    _trim_sessions(db, user)
    token = _generate_token()
    now = _now()
    row = UserSession(
        user_id=user.id,
        session_token=token,
        device_label=(device_label or "默认设备")[:100],
        last_active_at=now,
    )
    db.add(row)
    user.session_token = token
    db.commit()
    db.refresh(user)
    return token


def _migrate_legacy_token(db: Session, user: ChildUser, token: str) -> UserSession | None:
    if not user.session_token or user.session_token != token:
        return None
    existing = db.scalar(select(UserSession).where(UserSession.session_token == token))
    if existing:
        return existing
    _trim_sessions(db, user)
    row = UserSession(
        user_id=user.id,
        session_token=token,
        device_label="历史会话",
        last_active_at=_now(),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def validate_session(db: Session, user_id: int, token: str | None) -> bool:
    if not token:
        return False
    row = db.scalar(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.session_token == token,
        )
    )
    if not row:
        user = db.get(ChildUser, user_id)
        if user:
            migrated = _migrate_legacy_token(db, user, token)
            if migrated:
                row = migrated
        if not row:
            return False
    row.last_active_at = _now()
    db.commit()
    return True
