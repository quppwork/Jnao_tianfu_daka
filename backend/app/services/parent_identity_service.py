"""家长手机号身份解析 — 注册/登录/发短信统一判定（child_user + daka_member）。

「家长身份收敛」后端侧：凡按手机号判断「是否已注册 / 该登录谁 /
能否发短信」都应走本模块（或经 auth_service → parent_reconcile），
避免各入口各自查 ChildUser / daka_member 导致重复账号或误拦截。

wx_member_snapshot 仅用于微信 openid 查询，不参与浏览器短信注册拦截。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services import auth_service
from app.services.member_registry_service import find_daka_member_by_mobile
from app.services.sms_service import normalize_phone

SOURCE_CHILD_USER = "child_user"
SOURCE_DAKA_MEMBER = "daka_member"
SOURCE_NONE = "none"

ACTION_LOGIN = "login"
ACTION_REGISTER = "register"

MSG_ALREADY_REGISTERED = "该手机号已注册，请直接登录"
MSG_NOT_REGISTERED = "该手机号尚未注册，请先注册"


def resolve_parent_registration_state(db: Session, phone: str) -> dict:
    """返回 registered / source / action / message，供 API 与短信场景复用。"""
    from app.services.parent_reconcile_service import resolve_canonical_parent_for_login

    p = normalize_phone(phone)

    parent = resolve_canonical_parent_for_login(db, p)
    if parent:
        return {
            "registered": True,
            "source": SOURCE_CHILD_USER,
            "action": ACTION_LOGIN,
            "message": MSG_ALREADY_REGISTERED,
        }

    dm = find_daka_member_by_mobile(db, p)
    if dm:
        from app.db.models import ChildUser

        row = db.get(ChildUser, dm.parent_id)
        if row and row.role == auth_service.ROLE_PARENT and row.account_status != auth_service.ACCOUNT_DELETED:
            return {
                "registered": True,
                "source": SOURCE_DAKA_MEMBER,
                "action": ACTION_LOGIN,
                "message": MSG_ALREADY_REGISTERED,
            }

    return {
        "registered": False,
        "source": SOURCE_NONE,
        "action": ACTION_REGISTER,
        "message": "",
    }


def find_login_parent_user(db: Session, phone: str):
    """短信/密码登录解析家长 ChildUser（含 daka_member 兜底；removed 可恢复）。"""
    p = normalize_phone(phone)
    user = auth_service.find_parent_by_phone_for_login(db, p)
    if user:
        return user
    dm = find_daka_member_by_mobile(db, p)
    if dm:
        return auth_service.get_parent_for_login(db, dm.parent_id)
    return None


def assert_parent_can_register(db: Session, phone: str) -> None:
    state = resolve_parent_registration_state(db, phone)
    if state["action"] == ACTION_LOGIN:
        raise HTTPException(409, state["message"])


def assert_can_send_login_sms(db: Session, phone: str) -> None:
    state = resolve_parent_registration_state(db, phone)
    if state["action"] == ACTION_LOGIN:
        return
    raise HTTPException(404, MSG_NOT_REGISTERED)


def assert_can_login_sms(db: Session, phone: str) -> None:
    assert_can_send_login_sms(db, phone)
    if not find_login_parent_user(db, phone):
        raise HTTPException(404, MSG_NOT_REGISTERED)
