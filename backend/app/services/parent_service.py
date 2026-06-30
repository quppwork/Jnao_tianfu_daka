"""家长端 — 孩子账号分配与管理"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.password import hash_password
from app.db.models import ChildUser
from app.services import auth_service


def _require_parent(db: Session, parent_id: int) -> ChildUser:
    parent = auth_service.get_child_user(db, parent_id)
    if not parent or parent.role != auth_service.ROLE_PARENT:
        raise HTTPException(403, "需要家长账号")
    return parent


def get_quota(db: Session, parent_id: int) -> dict:
    parent = _require_parent(db, parent_id)
    limit = auth_service.get_parent_quota_limit(parent)
    used = auth_service.count_parent_children(db, parent_id)
    remaining = max(0, limit - used)
    return {
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "can_add": remaining > 0,
    }


def list_children(db: Session, parent_id: int) -> list[dict]:
    _require_parent(db, parent_id)
    children = auth_service.list_parent_children(db, parent_id)
    return [auth_service.child_summary(db, c) for c in children]


def create_child(
    db: Session,
    parent_id: int,
    *,
    login_name: str,
    nickname: str,
    password: str,
) -> ChildUser:
    parent = _require_parent(db, parent_id)
    if not auth_service.parent_can_add_child(db, parent):
        raise HTTPException(403, "孩子账号名额已满")

    login_name = login_name.strip()
    if auth_service.find_user_by_login_name(db, login_name):
        raise HTTPException(409, "该账号已被使用")

    child = auth_service.register_child(
        db,
        parent_phone=parent.parent_phone,
        nickname=nickname.strip(),
        login_name=login_name,
        password=password,
        role=auth_service.ROLE_STUDENT,
    )
    auth_service.bind_parent_child(db, parent_id, child.id)
    pj = dict(child.profile_json or {})
    pj["parentName"] = parent.nickname
    child.profile_json = pj
    db.commit()
    db.refresh(child)
    return child


def update_child(
    db: Session,
    parent_id: int,
    child_id: int,
    *,
    nickname: str | None = None,
    password: str | None = None,
) -> ChildUser:
    _require_parent(db, parent_id)
    if not auth_service.get_parent_child_bind(db, parent_id, child_id):
        raise HTTPException(404, "孩子不存在或未绑定")

    child = auth_service.get_child_user(db, child_id)
    if not child or child.role != auth_service.ROLE_STUDENT:
        raise HTTPException(404, "孩子不存在")

    if nickname is not None:
        child.nickname = nickname.strip()
    if password is not None:
        child.password_hash = hash_password(password)
    db.commit()
    db.refresh(child)
    return child


def delete_child(db: Session, parent_id: int, child_id: int) -> None:
    _require_parent(db, parent_id)
    bind = auth_service.get_parent_child_bind(db, parent_id, child_id)
    if not bind:
        raise HTTPException(404, "孩子不存在或未绑定")
    db.delete(bind)
    db.commit()


def get_child_detail(db: Session, parent_id: int, child_id: int) -> dict:
    _require_parent(db, parent_id)
    if not auth_service.get_parent_child_bind(db, parent_id, child_id):
        raise HTTPException(404, "孩子不存在或未绑定")
    child = auth_service.get_child_user(db, child_id)
    if not child:
        raise HTTPException(404, "孩子不存在")
    return auth_service.child_detail(db, child)
