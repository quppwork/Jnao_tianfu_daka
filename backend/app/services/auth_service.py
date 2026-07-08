"""用户注册 / 登录 — 家长手机号+密码、孩子账号+密码"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.password import hash_password, verify_password
from app.db.models import ChildUser, ParentChildBind, TalentAssessment, TrainingRecord

ROLE_PARENT = "parent"
ROLE_STUDENT = "student"
ROLE_ADMIN = "admin"
DEFAULT_CHILD_QUOTA = 5
ACCOUNT_ACTIVE = "active"
ACCOUNT_REMOVED = "removed"  # 管理员移出生产环境；数据保留，可再次登录恢复
ACCOUNT_DELETED = "deleted"  # 硬归档（如废弃管理员），不可恢复


def is_account_active(user: ChildUser | None) -> bool:
    if not user:
        return False
    return (getattr(user, "account_status", None) or ACCOUNT_ACTIVE) == ACCOUNT_ACTIVE


def is_account_removed(user: ChildUser | None) -> bool:
    if not user:
        return False
    return getattr(user, "account_status", None) == ACCOUNT_REMOVED


def reactivate_parent_with_children(db: Session, parent: ChildUser) -> None:
    """移出生产的家长再次登录时恢复本人及名下已移出的孩子（不删数据）。"""
    if parent.role != ROLE_PARENT:
        return
    if is_account_removed(parent):
        parent.account_status = ACCOUNT_ACTIVE
        parent.deleted_at = None
    child_ids = list(
        db.scalars(
            select(ParentChildBind.child_id).where(ParentChildBind.parent_id == parent.id)
        ).all()
    )
    for cid in child_ids:
        child = db.get(ChildUser, cid)
        if child and is_account_removed(child):
            child.account_status = ACCOUNT_ACTIVE
            child.deleted_at = None
    db.flush()


def reactivate_student_for_login(db: Session, student: ChildUser) -> None:
    if not is_account_removed(student):
        return
    bind = db.scalar(select(ParentChildBind).where(ParentChildBind.child_id == student.id))
    if bind:
        parent = db.get(ChildUser, bind.parent_id)
        if parent and parent.role == ROLE_PARENT:
            if is_account_removed(parent):
                reactivate_parent_with_children(db, parent)
                return
    student.account_status = ACCOUNT_ACTIVE
    student.deleted_at = None
    db.flush()


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
    commit: bool = True,
) -> ChildUser:
    if role == ROLE_PARENT:
        from app.services.parent_reconcile_service import resolve_canonical_parent_for_login

        if resolve_canonical_parent_for_login(db, parent_phone):
            from fastapi import HTTPException

            raise HTTPException(409, "该手机号已注册，请直接登录")
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
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def get_child_user(db: Session, child_user_id: int) -> ChildUser | None:
    user = db.get(ChildUser, child_user_id)
    if user and not is_account_active(user):
        return None
    return user


def get_parent_for_login(db: Session, user_id: int) -> ChildUser | None:
    """微信 OAuth 等：按 id 取家长，removed 时自动恢复。"""
    user = db.get(ChildUser, user_id)
    if not user or user.role != ROLE_PARENT:
        return None
    if user.account_status == ACCOUNT_DELETED:
        return None
    if is_account_removed(user):
        reactivate_parent_with_children(db, user)
        db.commit()
        db.refresh(user)
    return user if is_account_active(user) else None


def find_child_by_phone(db: Session, parent_phone: str, nickname: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.parent_phone == parent_phone,
            ChildUser.nickname == nickname,
            ChildUser.role == ROLE_STUDENT,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
    )


def find_parent_by_phone(db: Session, parent_phone: str) -> ChildUser | None:
    from app.services.parent_reconcile_service import resolve_canonical_parent

    return resolve_canonical_parent(db, parent_phone)


def find_parent_by_phone_for_login(db: Session, parent_phone: str) -> ChildUser | None:
    """登录/OAuth 用：可找到 removed 家长并在命中时自动恢复。"""
    from app.services.parent_reconcile_service import resolve_canonical_parent_for_login

    parent = resolve_canonical_parent_for_login(db, parent_phone)
    if parent and is_account_removed(parent):
        reactivate_parent_with_children(db, parent)
        db.commit()
        db.refresh(parent)
    return parent if is_account_active(parent) else None


def find_user_by_login_name(db: Session, login_name: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.login_name == login_name,
            ChildUser.role == ROLE_STUDENT,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
    )


def find_student_for_login(db: Session, login_name: str) -> ChildUser | None:
    """学生密码登录：含 removed 账号，命中后自动恢复。"""
    user = db.scalar(
        select(ChildUser).where(
            ChildUser.login_name == login_name,
            ChildUser.role == ROLE_STUDENT,
            ChildUser.account_status.in_((ACCOUNT_ACTIVE, ACCOUNT_REMOVED)),
        )
    )
    if not user:
        return None
    if is_account_removed(user):
        reactivate_student_for_login(db, user)
        db.commit()
        db.refresh(user)
    return user if is_account_active(user) else None


def find_admin_by_login_name(db: Session, login_name: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.login_name == login_name,
            ChildUser.role == ROLE_ADMIN,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
    )


def has_active_parent_bind(db: Session, child_id: int) -> bool:
    cnt = db.scalar(
        select(func.count())
        .select_from(ParentChildBind)
        .join(ChildUser, ChildUser.id == ParentChildBind.child_id)
        .where(
            ParentChildBind.child_id == child_id,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
    )
    return (cnt or 0) > 0


def login_parent_by_password(db: Session, parent_phone: str, password: str) -> ChildUser | None:
    user = find_parent_by_phone_for_login(db, parent_phone)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user

def login_student_by_password(db: Session, login_name: str, password: str) -> ChildUser | None:
    user = find_student_for_login(db, login_name)
    if not user or not verify_password(password, user.password_hash):
        return None
    if not has_active_parent_bind(db, user.id):
        return None
    return user


def login_admin_by_password(db: Session, login_name: str, password: str) -> ChildUser | None:
    user = find_admin_by_login_name(db, login_name.strip())
    if not user or not is_account_active(user):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def retire_other_admin_accounts(db: Session, *, keep_id: int) -> int:
    """废除 env 指定以外的所有活跃管理员，并吊销其全部 session。"""
    import logging

    from app.services.session_service import revoke_all_sessions

    logger = logging.getLogger("jnao")
    others = db.scalars(
        select(ChildUser).where(
            ChildUser.role == ROLE_ADMIN,
            ChildUser.id != keep_id,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
    ).all()
    if not others:
        return 0
    for admin in others:
        admin.account_status = ACCOUNT_DELETED
        revoke_all_sessions(db, admin.id)
        logger.info("已废除旧管理员 login_name=%s id=%s", admin.login_name, admin.id)
    db.commit()
    return len(others)


def ensure_admin_account(db: Session) -> ChildUser | None:
    """启动时确保管理员账号存在；凭据仅来自环境变量，并按 env 同步密码哈希。"""
    import logging
    import os

    from app.core.security import is_production

    logger = logging.getLogger("jnao")
    login_name = (os.getenv("ADMIN_LOGIN_NAME") or "").strip()
    password = (os.getenv("ADMIN_PASSWORD") or "").strip()
    if not login_name or not password:
        if is_production():
            raise RuntimeError("生产环境必须配置 ADMIN_LOGIN_NAME 与 ADMIN_PASSWORD")
        return None
    existing = find_admin_by_login_name(db, login_name)
    if existing:
        existing.nickname = existing.nickname or "管理员"
        pwd_changed = False
        if not verify_password(password, existing.password_hash):
            existing.password_hash = hash_password(password)
            pwd_changed = True
            logger.info("管理员密码已按环境变量更新")
        db.commit()
        db.refresh(existing)
        if pwd_changed:
            from app.services.session_service import revoke_all_sessions

            revoke_all_sessions(db, existing.id)
            db.commit()
        retire_other_admin_accounts(db, keep_id=existing.id)
        return existing
    user = register_child(
        db,
        parent_phone="admin",
        nickname="管理员",
        login_name=login_name,
        password=password,
        role=ROLE_ADMIN,
    )
    logger.info("已创建管理员账号 login_name=%s", login_name)
    retire_other_admin_accounts(db, keep_id=user.id)
    return user


def bind_parent_child(
    db: Session,
    parent_id: int,
    child_id: int,
    *,
    commit: bool = True,
) -> ParentChildBind:
    from fastapi import HTTPException

    existing = db.scalar(
        select(ParentChildBind).where(
            ParentChildBind.parent_id == parent_id,
            ParentChildBind.child_id == child_id,
        )
    )
    if existing:
        return existing
    other = db.scalar(select(ParentChildBind).where(ParentChildBind.child_id == child_id))
    if other:
        raise HTTPException(409, "孩子已绑定其他家长，请先解绑")
    row = ParentChildBind(parent_id=parent_id, child_id=child_id)
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def count_parent_children(db: Session, parent_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ParentChildBind)
        .join(ChildUser, ChildUser.id == ParentChildBind.child_id)
        .where(
            ParentChildBind.parent_id == parent_id,
            ChildUser.account_status == ACCOUNT_ACTIVE,
        )
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
            .where(
                ParentChildBind.parent_id == parent_id,
                ChildUser.account_status == ACCOUNT_ACTIVE,
            )
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
