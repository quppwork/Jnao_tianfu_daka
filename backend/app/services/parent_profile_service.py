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

LOGIN_CHANNEL_WECHAT = "wechat"
LOGIN_CHANNEL_STANDARD = "standard"


def _parent_block(profile: dict | None) -> tuple[dict, dict]:
    pj = dict(profile or {})
    parent = dict(pj.get("parent") or {})
    pj["parent"] = parent
    return pj, parent


def get_login_channel(user: ChildUser) -> str:
    pj, parent = _parent_block(user.profile_json)
    ch = (parent.get("login_channel") or LOGIN_CHANNEL_STANDARD).strip()
    return ch if ch in (LOGIN_CHANNEL_WECHAT, LOGIN_CHANNEL_STANDARD) else LOGIN_CHANNEL_STANDARD


def set_login_channel(user: ChildUser, channel: str) -> None:
    pj, parent = _parent_block(user.profile_json)
    parent["login_channel"] = channel
    user.profile_json = pj
    flag_modified(user, "profile_json")


def mark_phone_verified(user: ChildUser) -> None:
    now_iso = format_cst(datetime.now(TZ).replace(tzinfo=None))
    pj, parent = _parent_block(user.profile_json)
    parent["phone_verified_at"] = now_iso
    user.profile_json = pj
    flag_modified(user, "profile_json")


def get_parent_real_name(user: ChildUser) -> str | None:
    pj = user.profile_json or {}
    parent = pj.get("parent") or {}
    name = (parent.get("real_name") or "").strip()
    return name or None


def is_phone_verified(user: ChildUser) -> bool:
    pj = user.profile_json or {}
    return bool((pj.get("parent") or {}).get("phone_verified_at"))


def parent_profile_status(user: ChildUser) -> tuple[bool, list[str]]:
    if user.role != auth_service.ROLE_PARENT:
        return True, []
    missing: list[str] = []
    if not (user.nickname or "").strip():
        missing.append("nickname")
    if not get_parent_real_name(user):
        missing.append("real_name")
    return (len(missing) == 0, missing)


def parent_wechat_missing_fields(user: ChildUser) -> list[str]:
    missing: list[str] = []
    if not is_phone_verified(user):
        missing.append("phone")
    if not (user.nickname or "").strip():
        missing.append("nickname")
    if not get_parent_real_name(user):
        missing.append("real_name")
    if not user.password_hash:
        missing.append("password")
    return missing


def parent_account_ready(user: ChildUser) -> bool:
    if user.role != auth_service.ROLE_PARENT:
        return True
    if get_login_channel(user) != LOGIN_CHANNEL_WECHAT:
        complete, _ = parent_profile_status(user)
        return complete
    return len(parent_wechat_missing_fields(user)) == 0


def parent_next_step(user: ChildUser) -> str:
    if user.role != auth_service.ROLE_PARENT:
        return "home"
    if get_login_channel(user) == LOGIN_CHANNEL_WECHAT:
        missing = parent_wechat_missing_fields(user)
        if "phone" in missing:
            return "bind-phone"
        if missing:
            return "complete-profile"
        return "home"
    complete, _ = parent_profile_status(user)
    return "home" if complete else "complete-profile"


def parent_needs_company_verification(db: Session, user: ChildUser) -> bool:
    """Jnao 短信/密码注册且尚未完成微信 openid 进门验证。"""
    if user.role != auth_service.ROLE_PARENT:
        return False
    if parent_gate_passed(db, user):
        return False
    from app.services.member_registry_service import (
        CHANNEL_PASSWORD,
        CHANNEL_SMS,
        find_daka_member_by_parent,
    )

    dm = find_daka_member_by_parent(db, user.id)
    if dm and dm.register_channel in (CHANNEL_SMS, CHANNEL_PASSWORD):
        return True
    if not dm and get_login_channel(user) == LOGIN_CHANNEL_STANDARD:
        return True
    return False


def parent_gate_passed(db: Session, user: ChildUser) -> bool:
    """进门验证已通过：本地字段一次写入，进门后 API 只读。"""
    if user.role != auth_service.ROLE_PARENT:
        return True
    from app.services.member_registry_service import find_daka_member_by_parent
    from app.services.wechat_auth_service import get_bind_by_parent

    dm = find_daka_member_by_parent(db, user.id)
    if dm and dm.wechat_bound_at:
        return True
    if get_bind_by_parent(db, user.id):
        return True
    return False


def assert_parent_gate_passed(db: Session, user: ChildUser) -> None:
    import os

    if os.getenv("JNAO_TEST_SKIP_GATE") == "1":
        return
    if user.role != auth_service.ROLE_PARENT:
        return
    if not parent_gate_passed(db, user):
        raise HTTPException(
            403,
            "请先完成公司服务号手机验证（微信内一键登录或绑定手机）",
        )


def parent_auth_flags(db: Session, user: ChildUser) -> tuple[bool, bool, str]:
    """返回 (gate_passed, account_ready, next_step)。"""
    needs_company = parent_needs_company_verification(db, user)
    ready = parent_account_ready(user)
    step = parent_next_step(user)
    if needs_company:
        ready = False
        step = "bind-phone"
    return parent_gate_passed(db, user), ready, step


def parent_profile_to_dict(
    user: ChildUser,
    *,
    session_token: str | None = None,
    db: Session | None = None,
) -> dict:
    from app.core.session_cookie import maybe_strip_token

    complete, missing = parent_profile_status(user)
    channel = get_login_channel(user)
    if channel == LOGIN_CHANNEL_WECHAT:
        missing = parent_wechat_missing_fields(user)
        complete = len(missing) == 0
    gate_passed = True
    account_ready = parent_account_ready(user)
    next_step = parent_next_step(user)
    if db is not None and user.role == auth_service.ROLE_PARENT:
        gate_passed, account_ready, next_step = parent_auth_flags(db, user)
    out = {
        "id": user.id,
        "parent_phone": user.parent_phone,
        "nickname": user.nickname,
        "real_name": get_parent_real_name(user),
        "has_password": bool(user.password_hash),
        "phone_verified": is_phone_verified(user),
        "profile_complete": complete,
        "missing_fields": missing,
        "login_channel": channel,
        "account_ready": account_ready,
        "next_step": next_step,
        "gate_passed": gate_passed,
    }
    if session_token:
        out["session_token"] = maybe_strip_token(session_token)
    return out


def assert_parent_account_ready(user: ChildUser, db: Session | None = None) -> None:
    if user.role != auth_service.ROLE_PARENT:
        return
    if db is not None:
        assert_parent_gate_passed(db, user)
    if not parent_account_ready(user):
        step = parent_next_step(user)
        raise HTTPException(403, f"请先完善家长资料（{step}）")


def update_parent_profile(
    db: Session,
    user_id: int,
    *,
    nickname: str | None = None,
    real_name: str | None = None,
    password: str | None = None,
    old_password: str | None = None,
    require_password: bool = False,
) -> tuple[ChildUser, str | None]:
    user = db.get(ChildUser, user_id)
    if not user or user.role != auth_service.ROLE_PARENT:
        raise HTTPException(404, "家长不存在")
    if not auth_service.is_account_active(user):
        raise HTTPException(401, "账号已停用")

    new_session_token: str | None = None

    if nickname is not None:
        from app.core.nickname_policy import validate_nickname

        user.nickname = validate_nickname(nickname, field_label="昵称")

    pj, parent = _parent_block(user.profile_json)
    if real_name is not None:
        from app.core.nickname_policy import validate_real_name

        parent["real_name"] = validate_real_name(real_name)

    if password is not None:
        pwd = password.strip()
        if require_password and not pwd:
            raise HTTPException(400, "请设置登录密码")
        if pwd:
            from app.core.password import hash_password, verify_password
            from app.core.password_policy import validate_password_strength
            from app.services.session_service import issue_session, revoke_all_sessions

            validate_password_strength(pwd)
            if user.password_hash:
                old = (old_password or "").strip()
                if not old:
                    raise HTTPException(400, "修改密码需提供原密码")
                if not verify_password(old, user.password_hash):
                    raise HTTPException(401, "原密码错误")
            user.password_hash = hash_password(pwd)
            revoke_all_sessions(db, user.id)
            new_session_token = issue_session(db, user)

    user.profile_json = pj
    flag_modified(user, "profile_json")
    db.commit()
    db.refresh(user)
    return user, new_session_token


def login_parent_by_sms(db: Session, *, phone: str) -> ChildUser:
    from app.services.parent_identity_service import assert_can_login_sms, find_login_parent_user

    assert_can_login_sms(db, phone)
    existing = find_login_parent_user(db, phone)
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
    from app.services.auth_challenge_store import challenge_release_lock, challenge_try_lock
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user
    from app.services.parent_identity_service import assert_parent_can_register
    from app.services.sms_service import normalize_phone

    phone = normalize_phone(phone)
    lock_key = f"auth:register:{phone}"
    if not challenge_try_lock(lock_key, 30):
        raise HTTPException(429, "注册处理中，请稍后再试")
    try:
        assert_parent_can_register(db, phone)

        from app.core.nickname_policy import validate_nickname, validate_real_name
        from app.core.password_policy import validate_password_strength

        nick = validate_nickname(nickname, field_label="昵称")
        name = validate_real_name(real_name or "")
        pwd_value = validate_password_strength((password or "").strip())

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
            password=pwd_value,
            role=auth_service.ROLE_PARENT,
            child_quota=auth_service.DEFAULT_CHILD_QUOTA,
            commit=False,
        )
        user.profile_json = pj
        flag_modified(user, "profile_json")
        register_daka_member_from_user(db, user, register_channel=CHANNEL_SMS)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise
    finally:
        challenge_release_lock(lock_key)
