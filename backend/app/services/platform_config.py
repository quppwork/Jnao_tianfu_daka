"""平台配置 — 存储在管理员账号 profile_json.platform_config"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ChildUser
from app.services import auth_service

DEFAULT_LOGIN_POLICY = {
    "admin_max_devices": 3,
    "parent_max_devices": 1,
    "student_max_devices": 1,
}


def _config_admin(db: Session) -> ChildUser | None:
    return db.scalar(
        select(ChildUser)
        .where(
            ChildUser.role == auth_service.ROLE_ADMIN,
            ChildUser.account_status == auth_service.ACCOUNT_ACTIVE,
        )
        .order_by(ChildUser.id)
        .limit(1)
    )


def get_login_policy(db: Session) -> dict:
    admin = _config_admin(db)
    if not admin or not isinstance(admin.profile_json, dict):
        return dict(DEFAULT_LOGIN_POLICY)
    cfg = admin.profile_json.get("platform_config") or {}
    policy = cfg.get("login_policy") or {}
    return {
        "admin_max_devices": int(policy.get("admin_max_devices", DEFAULT_LOGIN_POLICY["admin_max_devices"])),
        "parent_max_devices": int(policy.get("parent_max_devices", DEFAULT_LOGIN_POLICY["parent_max_devices"])),
        "student_max_devices": int(policy.get("student_max_devices", DEFAULT_LOGIN_POLICY["student_max_devices"])),
    }


def max_devices_for_role(db: Session, role: str) -> int:
    policy = get_login_policy(db)
    if role == auth_service.ROLE_ADMIN:
        return max(1, policy["admin_max_devices"])
    if role == auth_service.ROLE_PARENT:
        return max(1, policy["parent_max_devices"])
    return max(1, policy["student_max_devices"])


def get_platform_config(db: Session) -> dict:
    return {"login_policy": get_login_policy(db)}


def update_platform_config(db: Session, admin_id: int, *, login_policy: dict) -> dict:
    admin = db.get(ChildUser, admin_id)
    if not admin or admin.role != auth_service.ROLE_ADMIN:
        raise ValueError("需要管理员权限")
    store = _config_admin(db)
    if not store:
        raise ValueError("未找到配置存储账号")
    pj = dict(store.profile_json or {})
    current = pj.get("platform_config") or {}
    lp = dict(current.get("login_policy") or DEFAULT_LOGIN_POLICY)
    if "admin_max_devices" in login_policy:
        lp["admin_max_devices"] = max(1, min(20, int(login_policy["admin_max_devices"])))
    if "parent_max_devices" in login_policy:
        lp["parent_max_devices"] = max(1, min(10, int(login_policy["parent_max_devices"])))
    if "student_max_devices" in login_policy:
        lp["student_max_devices"] = max(1, min(10, int(login_policy["student_max_devices"])))
    current["login_policy"] = lp
    pj["platform_config"] = current
    store.profile_json = pj
    flag_modified(store, "profile_json")
    db.commit()
    return get_platform_config(db)
