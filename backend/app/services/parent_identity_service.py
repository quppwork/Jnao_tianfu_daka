"""家长手机号身份解析 — 注册/登录/发短信统一判定（child_user + daka_member + wx_snapshot）"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WxMemberSnapshot
from app.services import auth_service
from app.services.member_registry_service import find_daka_member_by_mobile
from app.services.sms_service import normalize_phone

SOURCE_CHILD_USER = "child_user"
SOURCE_DAKA_MEMBER = "daka_member"
SOURCE_WX_SNAPSHOT = "wx_snapshot"
SOURCE_NONE = "none"

ACTION_LOGIN = "login"
ACTION_WECHAT_LOGIN = "wechat_login"
ACTION_REGISTER = "register"

MSG_ALREADY_REGISTERED = "该手机号已注册，请直接登录"
MSG_LEGACY_WECHAT = "该手机号已在老系统登记，请使用微信一键登录或验证码登录"
MSG_NOT_REGISTERED = "该手机号尚未注册，请先注册"


def lookup_snapshot_by_mobile(db: Session, phone: str) -> WxMemberSnapshot | None:
    p = normalize_phone(phone)
    return db.scalar(
        select(WxMemberSnapshot)
        .where(WxMemberSnapshot.mobile == p)
        .order_by(WxMemberSnapshot.id.desc())
        .limit(1)
    )


def resolve_parent_registration_state(db: Session, phone: str) -> dict:
    """返回 registered / source / action / message，供 API 与短信场景复用。"""
    p = normalize_phone(phone)

    parent = auth_service.find_parent_by_phone(db, p)
    if parent:
        return {
            "registered": True,
            "source": SOURCE_CHILD_USER,
            "action": ACTION_LOGIN,
            "message": MSG_ALREADY_REGISTERED,
        }

    dm = find_daka_member_by_mobile(db, p)
    if dm:
        user = auth_service.get_child_user(db, dm.parent_id)
        if user and auth_service.is_account_active(user):
            return {
                "registered": True,
                "source": SOURCE_DAKA_MEMBER,
                "action": ACTION_LOGIN,
                "message": MSG_ALREADY_REGISTERED,
            }

    snap = lookup_snapshot_by_mobile(db, p)
    if snap and (snap.mobile or "").strip():
        return {
            "registered": True,
            "source": SOURCE_WX_SNAPSHOT,
            "action": ACTION_WECHAT_LOGIN,
            "message": MSG_LEGACY_WECHAT,
        }

    return {
        "registered": False,
        "source": SOURCE_NONE,
        "action": ACTION_REGISTER,
        "message": "",
    }


def find_login_parent_user(db: Session, phone: str):
    """短信/密码登录解析家长 ChildUser（含 daka_member 兜底）。"""
    p = normalize_phone(phone)
    user = auth_service.find_parent_by_phone(db, p)
    if user:
        return user
    dm = find_daka_member_by_mobile(db, p)
    if dm:
        return auth_service.get_child_user(db, dm.parent_id)
    return None


def assert_parent_can_register(db: Session, phone: str) -> None:
    state = resolve_parent_registration_state(db, phone)
    if state["action"] == ACTION_LOGIN:
        raise HTTPException(409, state["message"])
    if state["action"] == ACTION_WECHAT_LOGIN:
        raise HTTPException(409, state["message"])


def assert_can_send_login_sms(db: Session, phone: str) -> None:
    state = resolve_parent_registration_state(db, phone)
    if state["action"] == ACTION_LOGIN:
        return
    if state["action"] == ACTION_WECHAT_LOGIN:
        raise HTTPException(404, state["message"])
    raise HTTPException(404, MSG_NOT_REGISTERED)


def assert_can_login_sms(db: Session, phone: str) -> None:
    assert_can_send_login_sms(db, phone)
    if not find_login_parent_user(db, phone):
        raise HTTPException(404, MSG_NOT_REGISTERED)
