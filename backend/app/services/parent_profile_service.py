"""家长资料完成度与验证码登录后建档"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser
from app.services import auth_service
from app.services.datetime_fmt import format_cst
from app.services.training_day import TZ


def _parent_block(profile: dict | None) -> dict:
    pj = dict(profile or {})
    parent = dict(pj.get("parent") or {})
    pj["parent"] = parent
    return pj, parent


def get_parent_real_name(user: ChildUser) -> str | None:
    pj = user.profile_json or {}
    parent = pj.get("parent") or {}
    name = (parent.get("real_name") or "").strip()
    return name or None


def parent_profile_status(user: ChildUser) -> tuple[bool, list[str]]:
    if user.role != auth_service.ROLE_PARENT:
        return True, []
    missing: list[str] = []
    if not (user.nickname or "").strip():
        missing.append("nickname")
    if not get_parent_real_name(user):
        missing.append("real_name")
    return (len(missing) == 0, missing)


def parent_profile_to_dict(user: ChildUser) -> dict:
    complete, missing = parent_profile_status(user)
    pj, parent = _parent_block(user.profile_json)
    return {
        "id": user.id,
        "parent_phone": user.parent_phone,
        "nickname": user.nickname,
        "real_name": parent.get("real_name"),
        "has_password": bool(user.password_hash),
        "phone_verified": bool(parent.get("phone_verified_at")),
        "profile_complete": complete,
        "missing_fields": missing,
    }


def update_parent_profile(
    db: Session,
    user_id: int,
    *,
    nickname: str | None = None,
    real_name: str | None = None,
    password: str | None = None,
) -> ChildUser:
    user = db.get(ChildUser, user_id)
    if not user or user.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")
    if not auth_service.is_account_active(user):
        raise HTTPException(401, "账号已停用")

    if nickname is not None:
        nick = nickname.strip()
        if not nick:
            raise HTTPException(400, "昵称不能为空")
        user.nickname = nick

    pj, parent = _parent_block(user.profile_json)
    if real_name is not None:
        name = real_name.strip()
        if not name:
            raise HTTPException(400, "姓名不能为空")
        parent["real_name"] = name

    if password is not None:
        pwd = password.strip()
        if pwd and len(pwd) < 6:
            raise HTTPException(400, "密码至少6位")
        if pwd:
            from app.core.password import hash_password

            user.password_hash = hash_password(pwd)
            from app.services.session_service import revoke_all_sessions

            revoke_all_sessions(db, user.id)

    user.profile_json = pj
    flag_modified(user, "profile_json")
    db.commit()
    db.refresh(user)
    return user


def login_parent_by_sms(db: Session, *, phone: str) -> ChildUser:
    existing = auth_service.find_parent_by_phone(db, phone)
    if not existing:
        raise HTTPException(404, "该手机号尚未注册，请先注册")

    now = datetime.now(TZ).replace(tzinfo=None)
    now_iso = format_cst(now)
    pj, parent = _parent_block(existing.profile_json)
    parent["phone_verified_at"] = now_iso
    existing.profile_json = pj
    flag_modified(existing, "profile_json")
    db.commit()
    db.refresh(existing)
    return existing


def register_parent_by_sms(
    db: Session,
    *,
    phone: str,
    nickname: str,
    real_name: str | None = None,
    password: str | None = None,
) -> ChildUser:
    if auth_service.find_parent_by_phone(db, phone):
        raise HTTPException(409, "该手机号已注册，请直接登录")

    nick = (nickname or "").strip()
    if not nick:
        raise HTTPException(400, "请填写昵称")
    name = (real_name or "").strip()
    if not name:
        raise HTTPException(400, "请填写真实姓名")

    now = datetime.now(TZ).replace(tzinfo=None)
    now_iso = format_cst(now)
    pj: dict = {
        "parent": {
            "real_name": name,
            "phone_verified_at": now_iso,
        }
    }
    user = auth_service.register_child(
        db,
        parent_phone=phone,
        nickname=nick,
        password=password.strip() if password and password.strip() else None,
        role=auth_service.ROLE_PARENT,
        child_quota=auth_service.DEFAULT_CHILD_QUOTA,
    )
    user.profile_json = pj
    flag_modified(user, "profile_json")
    db.commit()
    db.refresh(user)
    return user
