"""短信验证码 — 浏览器家长登录/注册（login/register）

微信内缺手机号走 m.jnao.com 绑手机页，不经本模块。
后期浏览器验证码单独接阿里云（SMS_PROVIDER=aliyun），与微信绑手机分离。
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.services import auth_service
from app.services.auth_challenge_store import (
    challenge_delete,
    challenge_get,
    challenge_get_count,
    challenge_incr,
    challenge_set,
)
from app.services.blacklist_service import check_auth_allowed, record_auth_failure
from app.services.captcha_service import verify_captcha
from app.services.training_day import TZ

logger = logging.getLogger("jnao")

PHONE_RE = re.compile(r"^1\d{10}$")
SMS_TTL = 300
SMS_SEND_INTERVAL = 60
SMS_DAILY_PER_PHONE = 10
SMS_HOURLY_PER_IP = 20
SMS_MAX_VERIFY_FAIL = 5
SMS_VERIFY_LOCK_TTL = 900
SCENE_LOGIN = "login"
SCENE_REGISTER = "register"
SCENE_BIND = "bind"


def _is_mock() -> bool:
    provider = (os.getenv("SMS_PROVIDER") or "mock").strip().lower()
    return provider in ("mock", "dev", "test", "")


def _mock_code() -> str:
    return (os.getenv("SMS_MOCK_CODE") or "88888").strip()[:6]


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def normalize_phone(phone: str) -> str:
    p = re.sub(r"\s+", "", phone or "").strip()
    if not PHONE_RE.match(p):
        raise HTTPException(400, "请输入正确的手机号")
    return p


def _sms_key(scene: str, phone: str) -> str:
    return f"auth:sms:{scene}:{phone}"


def _today_key() -> str:
    return datetime.now(TZ).strftime("%Y%m%d")


def _check_send_rate(phone: str, client_ip: str) -> None:
    last_key = f"auth:sms:last:{phone}"
    if challenge_get(last_key):
        raise HTTPException(429, "发送太频繁，请稍后再试")

    day_key = f"auth:sms:day:{phone}:{_today_key()}"
    if challenge_get_count(day_key) >= SMS_DAILY_PER_PHONE:
        raise HTTPException(429, "今日验证码发送次数已达上限")

    ip_key = f"auth:sms:ip:{client_ip}:{datetime.now(TZ).strftime('%Y%m%d%H')}"
    if client_ip and challenge_get_count(ip_key) >= SMS_HOURLY_PER_IP:
        raise HTTPException(429, "请求过于频繁，请稍后再试")


def _record_send(phone: str, client_ip: str) -> None:
    challenge_set(f"auth:sms:last:{phone}", {"sent": True}, SMS_SEND_INTERVAL)
    challenge_incr(f"auth:sms:day:{phone}:{_today_key()}", 86400)
    if client_ip:
        challenge_incr(
            f"auth:sms:ip:{client_ip}:{datetime.now(TZ).strftime('%Y%m%d%H')}",
            3600,
        )


def _generate_code() -> str:
    if _is_mock():
        return _mock_code()
    return f"{random.randint(0, 999999):06d}"


def _dispatch_company_sms(phone: str, code: str, scene: str) -> None:
    import httpx

    base = (os.getenv("COMPANY_SMS_BASE_URL") or "").strip().rstrip("/")
    if not base:
        raise HTTPException(503, "公司短信服务未配置 COMPANY_SMS_BASE_URL")
    path = (os.getenv("COMPANY_SMS_SEND_PATH") or "/send").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    headers = {}
    api_key = (os.getenv("COMPANY_SMS_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["X-Api-Key"] = api_key
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{base}{path}",
                json={"phone": phone, "code": code, "scene": scene},
                headers=headers,
            )
        if resp.status_code >= 400:
            logger.warning("Company SMS failed %s: %s", resp.status_code, resp.text[:200])
            raise HTTPException(502, "短信发送失败，请稍后再试")
    except httpx.HTTPError as e:
        logger.exception("Company SMS request error")
        raise HTTPException(502, "短信服务暂不可用") from e


def _dispatch_sms(phone: str, code: str, scene: str = SCENE_LOGIN) -> None:
    if _is_mock():
        logger.info("SMS mock → %s code=%s scene=%s", phone, code, scene)
        return
    provider = (os.getenv("SMS_PROVIDER") or "").strip().lower()
    if provider == "company":
        _dispatch_company_sms(phone, code, scene)
        return
    if provider == "aliyun":
        raise HTTPException(503, "阿里云短信尚未接入，请设置 SMS_PROVIDER=mock 或 company")
    if provider == "tencent":
        raise HTTPException(503, "腾讯云短信尚未接入，请设置 SMS_PROVIDER=mock 或 company")
    raise HTTPException(503, "短信服务未配置")


def send_sms_code(
    db: Session,
    *,
    phone: str,
    scene: str,
    client_ip: str = "",
    device_id: str = "",
    captcha_id: str | None = None,
    captcha_code: str | None = None,
) -> dict:
    phone = normalize_phone(phone)
    scene = (scene or SCENE_LOGIN).strip().lower()
    if scene not in (SCENE_LOGIN, SCENE_REGISTER, SCENE_BIND):
        raise HTTPException(400, "无效的发送场景")

    check_auth_allowed(db, client_ip=client_ip, phone=phone, device_id=device_id)

    exists = auth_service.find_parent_by_phone(db, phone) is not None
    if scene == SCENE_LOGIN and not exists:
        raise HTTPException(404, "该手机号尚未注册，请先注册")
    if scene == SCENE_REGISTER and exists:
        raise HTTPException(409, "该手机号已注册，请直接登录")
    if scene == SCENE_BIND:
        pass
    elif scene == SCENE_REGISTER:
        if not captcha_id or not captcha_code:
            raise HTTPException(400, "请先完成图形验证")
        verify_captcha(captcha_id, captcha_code, consume=True)
    # 登录发短信：仅靠限流 + 黑名单（无需图形码）

    _check_send_rate(phone, client_ip)
    code = _generate_code()
    challenge_set(
        _sms_key(scene, phone),
        {"code_hash": _hash_code(code), "fail_count": 0},
        SMS_TTL,
    )
    _record_send(phone, client_ip)
    _dispatch_sms(phone, code, scene)

    out: dict = {"ok": True, "expires_in": SMS_TTL, "resend_after": SMS_SEND_INTERVAL}
    if _is_mock() and os.getenv("SMS_MOCK_EXPOSE", "").strip() in ("1", "true", "yes"):
        out["debug_code"] = code
    return out


def verify_sms_code(phone: str, sms_code: str, scene: str) -> None:
    phone = normalize_phone(phone)
    scene = (scene or SCENE_LOGIN).strip().lower()
    if scene not in (SCENE_LOGIN, SCENE_REGISTER, SCENE_BIND):
        raise HTTPException(400, "无效的发送场景")
    if not sms_code or len(sms_code.strip()) < 4:
        raise HTTPException(400, "请输入短信验证码")

    lock_key = f"auth:sms:lock:{phone}:{scene}"
    if challenge_get(lock_key):
        raise HTTPException(429, "验证码错误次数过多，请稍后再试")

    row = challenge_get(_sms_key(scene, phone))
    if not row:
        raise HTTPException(400, "验证码已过期，请重新获取")

    if _hash_code(sms_code) != row.get("code_hash"):
        fail = int(row.get("fail_count") or 0) + 1
        if fail >= SMS_MAX_VERIFY_FAIL:
            challenge_set(lock_key, {"locked": True}, SMS_VERIFY_LOCK_TTL)
            challenge_delete(_sms_key(scene, phone))
            raise HTTPException(429, "验证码错误次数过多，请重新获取")
        row["fail_count"] = fail
        challenge_set(_sms_key(scene, phone), row, SMS_TTL)
        raise HTTPException(400, "验证码错误")

    challenge_delete(_sms_key(scene, phone))


def client_ip_from_request(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def device_id_from_request(request: Request) -> str:
    return (request.headers.get("x-device-id") or request.headers.get("X-Device-Id") or "").strip()[:64]
