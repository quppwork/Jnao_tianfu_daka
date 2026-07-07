"""微信公众号 OAuth 与家长登录 — 依赖 wx_member_snapshot / parent_wechat_bind"""

from __future__ import annotations

import logging
import os
import secrets
import urllib.parse
from datetime import datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.legacy_session import get_legacy_engine
from app.db.models import ChildUser, ParentWechatBind, WxMemberSnapshot
from app.services import auth_service
from app.services.auth_challenge_store import challenge_delete, challenge_get, challenge_set
from app.services.datetime_fmt import format_cst
from app.services.parent_profile_service import (
    LOGIN_CHANNEL_WECHAT,
    mark_phone_verified,
    parent_next_step,
    set_login_channel,
)
from app.services.sms_service import normalize_phone
from app.services.training_day import TZ

logger = logging.getLogger("jnao")

WX_STATE_TTL = 300
WX_BIND_TTL = 1800
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"


def wechat_configured() -> bool:
    app_id = (os.getenv("WECHAT_MP_APP_ID") or "").strip()
    secret = (os.getenv("WECHAT_MP_APP_SECRET") or "").strip()
    return bool(app_id and secret)


def wechat_app_id() -> str:
    return (os.getenv("WECHAT_MP_APP_ID") or "").strip()


def site_domain() -> str:
    return (os.getenv("SITE_DOMAIN") or "http://127.0.0.1:5185").strip().rstrip("/")


def oauth_redirect_uri() -> str:
    explicit = (os.getenv("WECHAT_OAUTH_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit
    api_base = site_domain()
    if ":5185" in api_base or ":5173" in api_base:
        api_base = "http://127.0.0.1:8012"
    return f"{api_base}/api/auth/wechat/callback"


def frontend_login_url(**params: str) -> str:
    base = site_domain()
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    return f"{base}/pages/login/index?{qs}" if qs else f"{base}/pages/login/index"


def frontend_wechat_error_url(message: str) -> str:
    qs = urllib.parse.urlencode({"wx_error": message[:240], "manual": "1"})
    return f"{site_domain()}/pages/login/index?{qs}"


def external_bind_mobile_url() -> str:
    """公司现有绑手机 H5（微信内跳转）。设 WECHAT_BIND_MOBILE_URL= 可关闭并回退 Jnao 内置绑手机。"""
    if "WECHAT_BIND_MOBILE_URL" in os.environ:
        return os.environ["WECHAT_BIND_MOBILE_URL"].strip()
    return "https://m.jnao.com/home/member/bindmobile.html"


def bind_mobile_return_url() -> str:
    custom = (os.getenv("WECHAT_BIND_MOBILE_RETURN_URL") or "").strip()
    if custom:
        return custom
    return f"{site_domain()}/pages/login/index?from=mp"


def build_external_bind_mobile_url() -> str:
    """绑手机页 URL，可选附带返回 Jnao 登录的参数"""
    base = external_bind_mobile_url()
    if not base:
        return ""
    param = (os.getenv("WECHAT_BIND_MOBILE_RETURN_PARAM") or "redirect").strip()
    ret = bind_mobile_return_url()
    if not param or not ret:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{param}={urllib.parse.quote(ret, safe='')}"


def use_external_bind_mobile() -> bool:
    return bool(external_bind_mobile_url())


def _state_key(state: str) -> str:
    return f"auth:wx:state:{state}"


def _bind_key(ticket: str) -> str:
    return f"auth:wx:pending:{ticket}"


def create_oauth_state(*, front_redirect: str = "") -> str:
    state = secrets.token_urlsafe(16)
    challenge_set(
        _state_key(state),
        {"front_redirect": front_redirect[:500]},
        WX_STATE_TTL,
    )
    return state


def consume_oauth_state(state: str) -> dict:
    row = challenge_get(_state_key(state))
    if not row:
        raise HTTPException(400, "授权状态已过期，请重新进入")
    challenge_delete(_state_key(state))
    return row


def build_oauth_url(*, front_redirect: str = "") -> str:
    if not wechat_configured():
        raise HTTPException(503, "微信公众号未配置")
    app_id = wechat_app_id()
    state = create_oauth_state(front_redirect=front_redirect)
    redirect_uri = urllib.parse.quote(oauth_redirect_uri(), safe="")
    return (
        "https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={app_id}&redirect_uri={redirect_uri}"
        "&response_type=code&scope=snsapi_base"
        f"&state={urllib.parse.quote(state, safe='')}#wechat_redirect"
    )


def exchange_code_for_openid(code: str) -> tuple[str, str | None]:
    if not wechat_configured():
        raise HTTPException(503, "微信公众号未配置")
    app_id = wechat_app_id()
    secret = (os.getenv("WECHAT_MP_APP_SECRET") or "").strip()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                WECHAT_TOKEN_URL,
                params={
                    "appid": app_id,
                    "secret": secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
    except httpx.HTTPError as e:
        logger.exception("WeChat token exchange failed")
        raise HTTPException(502, "微信授权服务暂不可用") from e

    if data.get("errcode"):
        errcode = int(data.get("errcode") or 0)
        errmsg = data.get("errmsg") or ""
        logger.warning("WeChat oauth error: %s %s", errcode, errmsg)
        if errcode == 40013:
            raise HTTPException(400, "微信 AppSecret 配置错误，请联系管理员")
        if errcode in (40029, 40163):
            raise HTTPException(400, "微信授权码已失效，请重新进入")
        if errcode == 10003:
            raise HTTPException(
                400,
                "微信回调域名未配置：请在公众平台设置网页授权域名为 jnaosoft.cn",
            )
        if errcode == 10005:
            raise HTTPException(400, "公众号无网页授权权限，请确认是已认证服务号")
        raise HTTPException(400, f"微信授权失败({errcode})，请重新进入")
    openid = (data.get("openid") or "").strip()
    if not openid:
        raise HTTPException(400, "未获取到微信 openid")
    unionid = (data.get("unionid") or "").strip() or None
    return openid, unionid


def _normalize_mobile(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw.strip() if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return None


def _row_to_snapshot(row: dict) -> dict:
    return {
        "wx_member_id": row.get("id") or row.get("wx_member_id"),
        "openid": row.get("openid"),
        "unionid": row.get("unionid"),
        "mobile": _normalize_mobile(row.get("mobile")),
        "nickname": row.get("nickname"),
        "truename": row.get("truename"),
    }


def upsert_snapshot(db: Session, data: dict) -> WxMemberSnapshot:
    openid = (data.get("openid") or "").strip()
    if not openid:
        raise ValueError("openid required")
    row = db.scalar(select(WxMemberSnapshot).where(WxMemberSnapshot.openid == openid))
    if not row:
        row = WxMemberSnapshot(openid=openid)
        db.add(row)
    row.wx_member_id = data.get("wx_member_id")
    row.unionid = data.get("unionid")
    row.mobile = _normalize_mobile(data.get("mobile")) if data.get("mobile") else None
    row.nickname = data.get("nickname")
    row.truename = data.get("truename")
    row.synced_at = datetime.now(TZ).replace(tzinfo=None)
    db.flush()
    return row


def fetch_legacy_member(openid: str) -> dict | None:
    engine = get_legacy_engine()
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id, openid, unionid, mobile, nickname, truename
                    FROM ys_wx_member
                    WHERE openid = :openid
                    LIMIT 1
                    """
                ),
                {"openid": openid},
            )
            row = result.mappings().first()
            if not row:
                return None
            return _row_to_snapshot(dict(row))
    except Exception as e:
        logger.warning("Legacy ys_wx_member lookup failed: %s", e)
        return None


def lookup_member(db: Session, openid: str, *, refresh_legacy: bool = False) -> WxMemberSnapshot | None:
    snap = db.scalar(select(WxMemberSnapshot).where(WxMemberSnapshot.openid == openid))
    need_legacy = refresh_legacy or snap is None or not snap.mobile
    if need_legacy:
        legacy = fetch_legacy_member(openid)
        if legacy:
            snap = upsert_snapshot(db, legacy)
            db.commit()
            db.refresh(snap)
            return snap
    if snap:
        return snap
    legacy = fetch_legacy_member(openid)
    if not legacy:
        return None
    snap = upsert_snapshot(db, legacy)
    db.commit()
    db.refresh(snap)
    return snap


def get_bind_by_openid(db: Session, openid: str) -> ParentWechatBind | None:
    app_id = wechat_app_id()
    if not app_id:
        return None
    return db.scalar(
        select(ParentWechatBind).where(
            ParentWechatBind.openid == openid,
            ParentWechatBind.app_id == app_id,
        )
    )


def upsert_wechat_bind(
    db: Session,
    *,
    parent_id: int,
    openid: str,
    unionid: str | None,
    wx_member_id: int | None,
) -> ParentWechatBind:
    app_id = wechat_app_id()
    row = get_bind_by_openid(db, openid)
    now = datetime.now(TZ).replace(tzinfo=None)
    if row:
        row.parent_id = parent_id
        row.unionid = unionid
        row.wx_member_id = wx_member_id
        row.last_login_at = now
    else:
        row = ParentWechatBind(
            parent_id=parent_id,
            openid=openid,
            unionid=unionid,
            wx_member_id=wx_member_id,
            app_id=app_id,
            last_login_at=now,
        )
        db.add(row)
    db.flush()
    return row


def _default_nickname(snap: WxMemberSnapshot | None, phone: str) -> str:
    if snap:
        for candidate in (snap.truename, snap.nickname):
            if candidate and str(candidate).strip():
                return str(candidate).strip()[:50]
    return f"家长{phone[-4:]}"


def ensure_parent_for_phone(
    db: Session,
    *,
    phone: str,
    snap: WxMemberSnapshot | None,
) -> ChildUser:
    existing = auth_service.find_parent_by_phone(db, phone)
    if existing:
        set_login_channel(existing, LOGIN_CHANNEL_WECHAT)
        mark_phone_verified(existing)
        if snap and snap.truename and not get_parent_real_name_safe(existing):
            pj, parent = _parent_block(existing.profile_json)
            parent["real_name"] = snap.truename.strip()
            existing.profile_json = pj
            flag_modified(existing, "profile_json")
        db.commit()
        db.refresh(existing)
        return existing

    nick = _default_nickname(snap, phone)
    real_name = (snap.truename or snap.nickname or nick).strip() if snap else nick
    now_iso = format_cst(datetime.now(TZ).replace(tzinfo=None))
    pj = {
        "parent": {
            "real_name": real_name[:50],
            "phone_verified_at": now_iso,
            "login_channel": LOGIN_CHANNEL_WECHAT,
        }
    }
    user = auth_service.register_child(
        db,
        parent_phone=phone,
        nickname=nick,
        role=auth_service.ROLE_PARENT,
        child_quota=auth_service.DEFAULT_CHILD_QUOTA,
    )
    user.profile_json = pj
    flag_modified(user, "profile_json")
    db.commit()
    db.refresh(user)
    return user


def _parent_block(profile: dict | None) -> tuple[dict, dict]:
    pj = dict(profile or {})
    parent = dict(pj.get("parent") or {})
    pj["parent"] = parent
    return pj, parent


def get_parent_real_name_safe(user: ChildUser) -> str | None:
    pj = user.profile_json or {}
    name = (pj.get("parent") or {}).get("real_name") or ""
    return name.strip() or None


def create_bind_ticket(*, openid: str, unionid: str | None, wx_member_id: int | None) -> str:
    ticket = secrets.token_urlsafe(18)
    challenge_set(
        _bind_key(ticket),
        {
            "openid": openid,
            "unionid": unionid,
            "wx_member_id": wx_member_id,
        },
        WX_BIND_TTL,
    )
    return ticket


def get_bind_ticket(ticket: str) -> dict:
    row = challenge_get(_bind_key(ticket))
    if not row:
        raise HTTPException(400, "绑定会话已过期，请重新从微信进入")
    return row


def consume_bind_ticket(ticket: str) -> dict:
    row = get_bind_ticket(ticket)
    challenge_delete(_bind_key(ticket))
    return row


def delete_bind_ticket(ticket: str) -> None:
    challenge_delete(_bind_key(ticket))


def resolve_wechat_login(
    db: Session,
    *,
    openid: str,
    unionid: str | None,
) -> tuple[ChildUser | None, str | None, str]:
    """返回 (user, bind_ticket, next_step)。user 为空表示需要先绑手机。"""
    bind = get_bind_by_openid(db, openid)
    if bind:
        user = auth_service.get_child_user(db, bind.parent_id)
        if user:
            set_login_channel(user, LOGIN_CHANNEL_WECHAT)
            upsert_wechat_bind(
                db,
                parent_id=user.id,
                openid=openid,
                unionid=unionid,
                wx_member_id=bind.wx_member_id,
            )
            db.commit()
            db.refresh(user)
            return user, None, parent_next_step(user)

    snap = lookup_member(db, openid, refresh_legacy=True)
    mobile = snap.mobile if snap else None
    if mobile:
        user = ensure_parent_for_phone(db, phone=mobile, snap=snap)
        upsert_wechat_bind(
            db,
            parent_id=user.id,
            openid=openid,
            unionid=unionid or (snap.unionid if snap else None),
            wx_member_id=snap.wx_member_id if snap else None,
        )
        db.commit()
        db.refresh(user)
        return user, None, parent_next_step(user)

    if use_external_bind_mobile():
        return None, None, "bind-phone"

    ticket = create_bind_ticket(
        openid=openid,
        unionid=unionid,
        wx_member_id=snap.wx_member_id if snap else None,
    )
    return None, ticket, "bind-phone"


def complete_bind_phone(
    db: Session,
    *,
    bind_ticket: str,
    phone: str,
) -> ChildUser:
    pending = consume_bind_ticket(bind_ticket)
    openid = pending["openid"]
    phone = normalize_phone(phone)
    snap = lookup_member(db, openid)
    user = ensure_parent_for_phone(db, phone=phone, snap=snap)
    upsert_wechat_bind(
        db,
        parent_id=user.id,
        openid=openid,
        unionid=pending.get("unionid"),
        wx_member_id=pending.get("wx_member_id"),
    )
    db.commit()
    db.refresh(user)
    return user
