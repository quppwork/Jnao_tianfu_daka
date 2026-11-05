"""登录安全黑名单 — 持久化在管理员 platform_config，支持解封"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.services.auth_challenge_store import challenge_get, challenge_get_count, challenge_incr, challenge_set
from app.services.datetime_fmt import format_cst
from app.services.platform_config import _config_admin
from app.services.training_day import TZ

LOGIN_FAIL_WINDOW = 900
LOGIN_FAIL_THRESHOLD = 15
LOGIN_NAME_FAIL_THRESHOLD = 10
BLACKLIST_TTL = 86400 * 7


def _blacklist_store(db: Session) -> dict:
    admin = _config_admin(db)
    if not admin:
        return {"ips": [], "phones": [], "devices": []}
    pj = admin.profile_json or {}
    cfg = pj.get("platform_config") or {}
    bl = cfg.get("security_blacklist") or {}
    return {
        "ips": list(bl.get("ips") or []),
        "phones": list(bl.get("phones") or []),
        "devices": list(bl.get("devices") or []),
    }


def _save_blacklist(db: Session, bl: dict) -> None:
    admin = _config_admin(db)
    if not admin:
        return
    pj = dict(admin.profile_json or {})
    cfg = dict(pj.get("platform_config") or {})
    cfg["security_blacklist"] = bl
    pj["platform_config"] = cfg
    admin.profile_json = pj
    flag_modified(admin, "profile_json")
    db.commit()


def _is_blocked(items: list, value: str) -> bool:
    if not value:
        return False
    now = datetime.now(TZ)
    for row in items:
        if (row.get("value") or "") != value:
            continue
        exp = row.get("expires_at")
        if exp:
            try:
                exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                if exp_dt.tzinfo:
                    exp_dt = exp_dt.astimezone(TZ).replace(tzinfo=None)
                if now.replace(tzinfo=None) > exp_dt:
                    continue
            except ValueError:
                pass
        return True
    return False


def check_auth_allowed(
    db: Session,
    *,
    client_ip: str = "",
    phone: str = "",
    device_id: str = "",
    login_name: str = "",
) -> None:
    bl = _blacklist_store(db)
    if _is_blocked(bl["ips"], client_ip):
        raise HTTPException(403, "当前网络已被限制访问，请联系管理员")
    if phone and _is_blocked(bl["phones"], phone):
        raise HTTPException(403, "该手机号已被限制，请联系管理员")
    if device_id and _is_blocked(bl["devices"], device_id):
        raise HTTPException(403, "当前设备已被限制，请联系管理员")
    if login_name:
        key = f"auth:fail:login:{login_name.strip()}"
        if challenge_get_count(key) >= LOGIN_NAME_FAIL_THRESHOLD:
            raise HTTPException(429, "登录尝试过于频繁，请稍后再试")


def record_auth_failure(
    db: Session,
    *,
    client_ip: str = "",
    phone: str = "",
    device_id: str = "",
    login_name: str = "",
    reason: str = "login_fail",
) -> None:
    if client_ip:
        key = f"auth:fail:ip:{client_ip}"
        n = challenge_incr(key, LOGIN_FAIL_WINDOW)
        if n >= LOGIN_FAIL_THRESHOLD:
            add_blacklist_entry(db, "ip", client_ip, reason=reason, ttl=BLACKLIST_TTL)
    if phone:
        key = f"auth:fail:phone:{phone}"
        n = challenge_incr(key, LOGIN_FAIL_WINDOW)
        if n >= LOGIN_FAIL_THRESHOLD:
            add_blacklist_entry(db, "phone", phone, reason=reason, ttl=BLACKLIST_TTL)
    if device_id:
        key = f"auth:fail:device:{device_id}"
        n = challenge_incr(key, LOGIN_FAIL_WINDOW)
        if n >= LOGIN_FAIL_THRESHOLD:
            add_blacklist_entry(db, "device", device_id, reason=reason, ttl=BLACKLIST_TTL)
    if login_name:
        ln = login_name.strip()
        if ln:
            key = f"auth:fail:login:{ln}"
            challenge_incr(key, LOGIN_FAIL_WINDOW)


def clear_auth_failures(
    *,
    client_ip: str = "",
    phone: str = "",
    device_id: str = "",
    login_name: str = "",
) -> None:
    from app.services.auth_challenge_store import challenge_delete

    if client_ip:
        challenge_delete(f"auth:fail:ip:{client_ip}")
    if phone:
        challenge_delete(f"auth:fail:phone:{phone}")
    if device_id:
        challenge_delete(f"auth:fail:device:{device_id}")
    if login_name:
        challenge_delete(f"auth:fail:login:{login_name.strip()}")


def add_blacklist_entry(
    db: Session,
    kind: str,
    value: str,
    *,
    reason: str = "auto",
    ttl: int | None = BLACKLIST_TTL,
    created_by: str = "system",
) -> None:
    if not value:
        return
    bucket_map = {"ip": "ips", "phone": "phones", "device": "devices"}
    bucket = bucket_map.get(kind, kind)
    bl = _blacklist_store(db)
    items = [r for r in bl.get(bucket, []) if r.get("value") != value]
    now = datetime.now(TZ).replace(tzinfo=None)
    exp = None
    if ttl and ttl > 0:
        from datetime import timedelta

        exp = format_cst(now + timedelta(seconds=ttl))
    items.insert(
        0,
        {
            "value": value,
            "reason": reason,
            "created_at": format_cst(now),
            "expires_at": exp,
            "created_by": created_by,
        },
    )
    bl[bucket] = items[:200]
    _save_blacklist(db, bl)


def remove_blacklist_entry(db: Session, kind: str, value: str) -> bool:
    bucket_map = {"ip": "ips", "phone": "phones", "device": "devices"}
    bucket = bucket_map.get(kind, kind)
    bl = _blacklist_store(db)
    before = len(bl.get(bucket) or [])
    bl[bucket] = [r for r in (bl.get(bucket) or []) if r.get("value") != value]
    if len(bl[bucket]) == before:
        return False
    _save_blacklist(db, bl)
    if bucket == "ips":
        clear_auth_failures(client_ip=value)
    elif bucket == "phones":
        clear_auth_failures(phone=value)
    elif bucket == "devices":
        clear_auth_failures(device_id=value)
    return True


def list_blacklist(db: Session) -> dict:
    return _blacklist_store(db)
