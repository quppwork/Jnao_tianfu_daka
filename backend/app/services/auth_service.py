"""用户注册 / 登录 — 家长手机号+密码、孩子账号+密码"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.password import hash_password, verify_password
from app.db.models import ChildUser, ParentChildBind, TalentAssessment, TrainingRecord

ROLE_PARENT = "parent"
ROLE_STUDENT = "student"
DEFAULT_CHILD_QUOTA = 5


def _generate_session_token() -> str:
    """生成 64 字符随机 session token，新登录时旧 token 失效"""
    return secrets.token_hex(32)


def _refresh_session_token(db: Session, user: ChildUser) -> str:
    """刷新用户 session token 并持久化，返回新 token"""
    token = _generate_session_token()
    user.session_token = token
    db.commit()
    db.refresh(user)
    return token


def register_child(
    db: Session,
    *,
    parent_phone: str,
    nickname: str,
    jnao_uid: str | None = None,
    password: str | None = None,
    role: str = ROLE_STUDENT,
    login_name: str | None = None,
    child_quota: int | None = None,
) -> ChildUser:
    user = ChildUser(
        parent_phone=parent_phone,
        nickname=nickname,
        jnao_uid=jnao_uid,
        role=role,
        login_name=login_name,
        password_hash=hash_password(password) if password else None,
        child_quota=child_quota if role == ROLE_PARENT else None,
        session_token=_generate_session_token(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_child_user(db: Session, child_user_id: int) -> ChildUser | None:
    return db.get(ChildUser, child_user_id)


def find_child_by_phone(db: Session, parent_phone: str, nickname: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.parent_phone == parent_phone,
            ChildUser.nickname == nickname,
            ChildUser.role == ROLE_STUDENT,
        )
    )


def find_parent_by_phone(db: Session, parent_phone: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.parent_phone == parent_phone,
            ChildUser.role == ROLE_PARENT,
        )
    )


def find_user_by_login_name(db: Session, login_name: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.login_name == login_name,
            ChildUser.role == ROLE_STUDENT,
        )
    )


def login_parent_by_password(db: Session, parent_phone: str, password: str) -> ChildUser | None:
    user = find_parent_by_phone(db, parent_phone)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def login_student_by_password(db: Session, login_name: str, password: str) -> ChildUser | None:
    user = find_user_by_login_name(db, login_name)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def bind_parent_child(db: Session, parent_id: int, child_id: int) -> ParentChildBind:
    existing = db.scalar(
        select(ParentChildBind).where(
            ParentChildBind.parent_id == parent_id,
            ParentChildBind.child_id == child_id,
        )
    )
    if existing:
        return existing
    row = ParentChildBind(parent_id=parent_id, child_id=child_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def count_parent_children(db: Session, parent_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ParentChildBind)
        .where(ParentChildBind.parent_id == parent_id)
    ) or 0


def get_parent_quota_limit(parent: ChildUser) -> int:
    if parent.child_quota is not None and parent.child_quota > 0:
        return parent.child_quota
    return DEFAULT_CHILD_QUOTA


def parent_can_add_child(db: Session, parent: ChildUser) -> bool:
    limit = get_parent_quota_limit(parent)
    used = count_parent_children(db, parent.id)
    return used < limit


def list_parent_children(db: Session, parent_id: int) -> list[ChildUser]:
    return list(
        db.scalars(
            select(ChildUser)
            .join(ParentChildBind, ParentChildBind.child_id == ChildUser.id)
            .where(ParentChildBind.parent_id == parent_id)
            .order_by(ChildUser.id)
        ).all()
    )


def get_parent_child_bind(db: Session, parent_id: int, child_id: int) -> ParentChildBind | None:
    return db.scalar(
        select(ParentChildBind).where(
            ParentChildBind.parent_id == parent_id,
            ParentChildBind.child_id == child_id,
        )
    )


def _latest_talent(db: Session, child_id: int) -> str | None:
    row = db.scalar(
        select(TalentAssessment.talent_primary)
        .where(TalentAssessment.child_user_id == child_id)
        .order_by(TalentAssessment.id.desc())
        .limit(1)
    )
    return row


def _training_days(db: Session, child_id: int) -> int:
    from app.services.child_training_state import get_training_progress

    user = db.get(ChildUser, child_id)
    if not user:
        return 0
    progress = get_training_progress(user)
    return int(progress.get("training_days") or 0)


def _checkin_count(db: Session, child_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(TrainingRecord).where(TrainingRecord.child_user_id == child_id)
    ) or 0


def child_summary(db: Session, child: ChildUser) -> dict:
    profile = child.profile_json or {}
    learner = profile.get("learner") or {}
    return {
        "id": child.id,
        "login_name": child.login_name,
        "nickname": child.nickname,
        "talent": _latest_talent(db, child.id),
        "training_days": _training_days(db, child.id),
        "checkins": _checkin_count(db, child.id),
        "grade": learner.get("grade"),
        "age": learner.get("age"),
        "region": learner.get("region"),
    }


def child_detail(db: Session, child: ChildUser) -> dict:
    base = child_summary(db, child)
    profile = child.profile_json or {}
    learner = profile.get("learner") or {}
    base["school_stage"] = learner.get("school_stage")
    return base
