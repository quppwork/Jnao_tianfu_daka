"""多端登录会话管理 — 用户端签发 JWT，Admin 仍用 opaque Cookie token"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.jwt_tokens import decode_access_token, looks_like_jwt, mint_access_token
from app.db.models import ChildUser, UserSession
from app.services import auth_service
from app.services.datetime_fmt import format_cst
from app.services.platform_config import max_devices_for_role
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


def revoke_session_token(db: Session, user_id: int, token: str | None) -> bool:
    """撤销当前设备会话（JWT 或 opaque）。成功返回 True。"""
    if not token:
        return False
    jti = token
    if looks_like_jwt(token):
        try:
            payload = decode_access_token(token)
        except Exception:
            return False
        if str(payload.get("sub")) != str(user_id):
            return False
        jti = str(payload.get("jti") or "")
        sid = payload.get("sid")
        if sid is not None:
            row = db.get(UserSession, int(sid))
            if row and row.user_id == user_id:
                db.delete(row)
                user = db.get(ChildUser, user_id)
                if user and user.session_token == row.session_token:
                    # 若删的是镜像最新会话，清掉；其它设备仍有效
                    newest = db.scalar(
                        select(UserSession)
                        .where(UserSession.user_id == user_id)
                        .order_by(UserSession.last_active_at.desc())
                    )
                    user.session_token = newest.session_token if newest else None
                return True
    if not jti:
        return False
    row = db.scalar(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.session_token == jti,
        )
    )
    if not row:
        return False
    db.delete(row)
    user = db.get(ChildUser, user_id)
    if user and user.session_token == jti:
        newest = db.scalar(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.last_active_at.desc())
        )
        user.session_token = newest.session_token if newest else None
    return True


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
    """签发新会话。家长/学生返回 JWT；管理员返回 opaque token（Cookie）。"""
    _trim_sessions(db, user)
    jti = _generate_token()
    now = _now()
    row = UserSession(
        user_id=user.id,
        session_token=jti,
        device_label=(device_label or "默认设备")[:100],
        last_active_at=now,
    )
    db.add(row)
    user.session_token = jti
    db.commit()
    db.refresh(user)
    db.refresh(row)
    role = user.role or auth_service.ROLE_STUDENT
    if role == auth_service.ROLE_ADMIN:
        return jti
    return mint_access_token(
        user_id=user.id,
        role=role,
        sid=row.id,
        jti=jti,
    )


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


def _touch_row(db: Session, row: UserSession) -> None:
    now = _now()
    touch_sec = 300
    raw = (os.getenv("SESSION_TOUCH_INTERVAL_SEC") or "").strip()
    if raw:
        try:
            touch_sec = max(0, int(raw))
        except ValueError:
            touch_sec = 300
    last = row.last_active_at
    if touch_sec > 0 and last is not None:
        try:
            delta = (now - last).total_seconds()
        except TypeError:
            delta = touch_sec
        if delta < touch_sec:
            return
    row.last_active_at = now
    db.commit()


def validate_session(db: Session, user_id: int, token: str | None) -> bool:
    if not token:
        return False

    if looks_like_jwt(token):
        try:
            payload = decode_access_token(token)
        except Exception:
            return False
        if str(payload.get("sub")) != str(user_id):
            return False
        jti = str(payload.get("jti") or "")
        sid = payload.get("sid")
        if not jti or sid is None:
            return False
        row = db.get(UserSession, int(sid))
        if not row or row.user_id != user_id or row.session_token != jti:
            return False
        _touch_row(db, row)
        return True

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
    _touch_row(db, row)
    return True
