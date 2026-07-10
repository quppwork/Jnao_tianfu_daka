"""微信公众号 OAuth 与家长登录 — 依赖 wx_member_snapshot / parent_wechat_bind"""

from __future__ import annotations

import json
import logging
import os
import secrets
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.legacy_session import get_legacy_engine
from app.db.models import ChildUser, DakaMember, ParentWechatBind, WxMemberSnapshot
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
WX_LOGIN_EXCHANGE_TTL = 120
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"

_LEGACY_TIME_COLUMNS = (
    "update_time",
    "updatetime",
    "updated_at",
    "modify_time",
    "u_time",
    "lastupdate",
    "last_time",
)


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


def bind_mobile_return_url(bind_ticket: str | None = None) -> str:
    custom = (os.getenv("WECHAT_BIND_MOBILE_RETURN_URL") or "").strip()
    base = custom if custom else f"{site_domain()}/pages/login/index?from=mp"
    if bind_ticket:
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}bind_ticket={urllib.parse.quote(bind_ticket, safe='')}"
    return base


def build_external_bind_mobile_url(*, bind_ticket: str | None = None) -> str:
    """绑手机页 URL，可选附带返回 Jnao 登录的参数"""
    base = external_bind_mobile_url()
    if not base:
        return ""
    param = (os.getenv("WECHAT_BIND_MOBILE_RETURN_PARAM") or "redirect").strip()
    ret = bind_mobile_return_url(bind_ticket)
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


def _login_exchange_key(ticket: str) -> str:
    return f"auth:wx:login:{ticket}"


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
    oid = (openid or "").strip()
    if not oid:
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
                {"openid": oid},
            )
            row = result.mappings().first()
            if not row:
                return None
            return _row_to_snapshot(dict(row))
    except Exception as e:
        logger.warning("Legacy ys_wx_member lookup failed: %s", e)
        return None


def fetch_legacy_member_by_mobile(mobile: str) -> dict | None:
    """老库按手机号查 ys_wx_member（用于 openid 与手机号对齐诊断/补同步）。"""
    engine = get_legacy_engine()
    if not engine:
        return None
    phone = _normalize_mobile(mobile)
    if not phone:
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT id, openid, unionid, mobile, nickname, truename
                    FROM ys_wx_member
                    WHERE REPLACE(REPLACE(mobile, ' ', ''), '-', '') = :phone
                       OR mobile = :phone
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"phone": phone},
            )
            row = result.mappings().first()
            if not row:
                return None
            return _row_to_snapshot(dict(row))
    except Exception as e:
        logger.warning("Legacy ys_wx_member mobile lookup failed: %s", e)
        return None


def sync_snapshot_from_legacy(
    db: Session,
    *,
    openid: str,
    mobile: str | None = None,
) -> WxMemberSnapshot | None:
    """将老库 ys_wx_member 字段写入 wx_member_snapshot（openid 优先，可按手机号补查）。"""
    oid = (openid or "").strip()
    if not oid:
        return None
    data = fetch_legacy_member(oid)
    if not data and mobile:
        data = fetch_legacy_member_by_mobile(mobile)
    if not data:
        return lookup_member_local(db, oid)
    if mobile and not data.get("mobile"):
        data["mobile"] = _normalize_mobile(mobile)
    snap = upsert_snapshot(db, data)
    db.commit()
    db.refresh(snap)
    return snap


def lookup_member_local(db: Session, openid: str) -> WxMemberSnapshot | None:
    """仅查本地 wx_member_snapshot。"""
    return db.scalar(select(WxMemberSnapshot).where(WxMemberSnapshot.openid == openid))


def lookup_member_for_oauth(db: Session, openid: str) -> WxMemberSnapshot | None:
    """OAuth 仅查本地 wx_member_snapshot；老库请走定时同步 sync_wx_member_snapshot。"""
    return lookup_member_local(db, openid)


def lookup_snapshot_by_mobile(db: Session, mobile: str) -> WxMemberSnapshot | None:
    phone = _normalize_mobile(mobile)
    if not phone:
        return None
    return db.scalar(
        select(WxMemberSnapshot)
        .where(WxMemberSnapshot.mobile == phone)
        .order_by(WxMemberSnapshot.id.desc())
        .limit(1)
    )


def lookup_member(db: Session, openid: str, *, refresh_legacy: bool = False) -> WxMemberSnapshot | None:
    """兼容旧调用；refresh_legacy 时同 lookup_member_for_oauth。"""
    if refresh_legacy:
        return lookup_member_for_oauth(db, openid)
    return lookup_member_local(db, openid)


def _sync_state_path() -> Path:
    custom = (os.getenv("WX_SYNC_STATE_FILE") or "").strip()
    if custom:
        return Path(custom)
    return Path("/app/data/wx_sync_state.json")


def _load_sync_state() -> dict:
    path = _sync_state_path()
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Load wx sync state failed: %s", e)
    return {}


def _save_sync_state(state: dict) -> None:
    path = _sync_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Save wx sync state failed: %s", e)


def _legacy_table_columns(engine) -> set[str]:
    from sqlalchemy import inspect

    insp = inspect(engine)
    try:
        return {c["name"] for c in insp.get_columns("ys_wx_member")}
    except Exception:
        return set()


def _pick_legacy_time_column(engine) -> str | None:
    cols = _legacy_table_columns(engine)
    for name in _LEGACY_TIME_COLUMNS:
        if name in cols:
            return name
    return None


def _stats_from_rows(db: Session, rows: list[dict]) -> dict[str, int]:
    stats = {"total": 0, "with_mobile": 0, "without_mobile": 0}
    for data in rows:
        snap = upsert_snapshot(db, data)
        stats["total"] += 1
        if snap.mobile:
            stats["with_mobile"] += 1
        else:
            stats["without_mobile"] += 1
    return stats


def fetch_legacy_members_incremental(
    *,
    last_id: int = 0,
    since_time: str | None = None,
) -> tuple[list[dict], str, int | None, str | None]:
    """增量拉取老库会员。返回 (rows, mode, new_last_id, new_since_time)。"""
    engine = get_legacy_engine()
    if not engine:
        return [], "none", last_id, since_time

    time_col = _pick_legacy_time_column(engine)
    select_cols = "id, openid, unionid, mobile, nickname, truename"
    rows_raw: list[dict] = []
    mode = "id"

    with engine.connect() as conn:
        if time_col and since_time:
            mode = "time"
            sql = f"""
                SELECT {select_cols}, {time_col} AS _sync_time
                FROM ys_wx_member
                WHERE openid IS NOT NULL AND openid != ''
                  AND {time_col} > :since
                ORDER BY {time_col}
            """
            rows_raw = [dict(r) for r in conn.execute(text(sql), {"since": since_time}).mappings().all()]
        else:
            sql = f"""
                SELECT {select_cols}
                FROM ys_wx_member
                WHERE openid IS NOT NULL AND openid != '' AND id > :last_id
                ORDER BY id
            """
            rows_raw = [dict(r) for r in conn.execute(text(sql), {"last_id": last_id}).mappings().all()]

    rows = [_row_to_snapshot(r) for r in rows_raw]
    new_last_id = last_id
    new_since = since_time
    for raw, data in zip(rows_raw, rows):
        wid = data.get("wx_member_id")
        if isinstance(wid, int) and wid > new_last_id:
            new_last_id = wid
        if mode == "time":
            ts = raw.get("_sync_time")
            if ts is not None:
                new_since = str(ts)

    if mode == "time" and rows and new_since == since_time:
        ts = rows_raw[-1].get("_sync_time")
        if ts is not None:
            new_since = str(ts)

    return rows, mode, new_last_id, new_since


def sync_wx_members_incremental(db: Session) -> dict[str, int | str]:
    """B：增量同步（新 id 或 update_time 变更）。"""
    if not get_legacy_engine():
        raise RuntimeError("LEGACY_DATABASE_URL 未配置，无法同步")

    state = _load_sync_state()
    last_id = int(state.get("last_id") or 0)
    if last_id <= 0:
        last_id = int(db.scalar(select(func.max(WxMemberSnapshot.wx_member_id))) or 0)
    since_time = state.get("last_time")

    rows, mode, new_last_id, new_since = fetch_legacy_members_incremental(
        last_id=last_id,
        since_time=since_time if isinstance(since_time, str) else None,
    )
    stats = _stats_from_rows(db, rows)
    stats["mode"] = mode
    db.commit()

    if rows:
        _save_sync_state({"last_id": new_last_id, "last_time": new_since})
    elif not state:
        _save_sync_state({"last_id": last_id, "last_time": since_time})

    return stats


def fetch_all_legacy_members() -> list[dict]:
    engine = get_legacy_engine()
    if not engine:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, openid, unionid, mobile, nickname, truename
                FROM ys_wx_member
                WHERE openid IS NOT NULL AND openid != ''
                """
            )
        ).mappings().all()
    return [_row_to_snapshot(dict(row)) for row in rows]


def sync_wx_members_from_legacy(db: Session) -> dict[str, int | str]:
    """从 db_fz_jingnao.ys_wx_member 全量拉取到 wx_member_snapshot（定时任务专用）。"""
    rows = fetch_all_legacy_members()
    if not rows and not get_legacy_engine():
        raise RuntimeError("LEGACY_DATABASE_URL 未配置，无法同步")

    stats = _stats_from_rows(db, rows)
    stats["mode"] = "full"
    db.commit()

    max_id = max((r.get("wx_member_id") or 0 for r in rows), default=0)
    _save_sync_state({"last_id": max_id, "last_time": _load_sync_state().get("last_time")})
    return stats


def sync_snapshot_for_openid(db: Session, openid: str, *, mobile: str | None = None) -> WxMemberSnapshot | None:
    """公司绑手机完成后单条同步老库 → 本地 snapshot（不阻塞日常 API）。"""
    snap = sync_snapshot_from_legacy(db, openid=openid, mobile=mobile)
    if snap:
        logger.info(
            "single sync wx snapshot openid=%s… mobile=%s",
            (openid or "")[:10],
            snap.mobile or "-",
        )
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


def get_bind_by_parent(db: Session, parent_id: int) -> ParentWechatBind | None:
    app_id = wechat_app_id()
    if not app_id:
        return None
    return db.scalar(
        select(ParentWechatBind).where(
            ParentWechatBind.parent_id == parent_id,
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
    by_openid = get_bind_by_openid(db, openid)
    by_parent = get_bind_by_parent(db, parent_id)
    if by_openid and by_openid.parent_id != parent_id:
        raise HTTPException(409, "该微信已绑定其他家长账号")
    if by_parent and by_parent.openid != openid:
        raise HTTPException(409, "该家长账号已绑定其他微信")
    now = datetime.now(TZ).replace(tzinfo=None)
    row = by_openid or by_parent
    if row:
        row.parent_id = parent_id
        row.openid = openid
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


def finalize_wechat_login_user(
    db: Session,
    user: ChildUser,
    *,
    openid: str,
    unionid: str | None = None,
    snap: WxMemberSnapshot | None = None,
) -> str:
    """同步微信绑定与 daka_member；平台已注册手机号视为已验证，返回真实 next_step。"""
    from app.services.member_registry_service import (
        CHANNEL_WECHAT,
        CHANNEL_WECHAT_LEGACY,
        find_daka_member_by_parent,
        register_daka_member_from_user,
    )

    oid = (openid or "").strip()
    if not oid:
        return parent_next_step(user)

    set_login_channel(user, LOGIN_CHANNEL_WECHAT)
    dm = find_daka_member_by_parent(db, user.id)
    if dm and dm.mobile:
        mark_phone_verified(user)
    elif (user.parent_phone or "").strip():
        mark_phone_verified(user)

    wx_mid = snap.wx_member_id if snap else (dm.legacy_wx_member_id if dm else None)
    upsert_wechat_bind(
        db,
        parent_id=user.id,
        openid=oid,
        unionid=unionid,
        wx_member_id=wx_mid,
    )
    register_daka_member_from_user(
        db,
        user,
        register_channel=CHANNEL_WECHAT_LEGACY if snap else CHANNEL_WECHAT,
        openid=oid,
        unionid=unionid,
        legacy_matched=bool(snap),
        legacy_wx_member_id=wx_mid,
    )
    from app.services.member_registry_service import mark_parent_gate_passed

    mark_parent_gate_passed(db, user, company_verified=True)
    db.commit()
    db.refresh(user)
    return parent_next_step(user)


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
    openid: str | None = None,
    unionid: str | None = None,
) -> ChildUser:
    from app.services.member_registry_service import (
        CHANNEL_WECHAT,
        CHANNEL_WECHAT_LEGACY,
        register_daka_member_from_user,
    )

    existing = auth_service.find_parent_by_phone_for_login(db, phone)
    if existing:
        set_login_channel(existing, LOGIN_CHANNEL_WECHAT)
        mark_phone_verified(existing)
        if snap and snap.truename and not get_parent_real_name_safe(existing):
            pj, parent = _parent_block(existing.profile_json)
            parent["real_name"] = snap.truename.strip()
            existing.profile_json = pj
            flag_modified(existing, "profile_json")
        register_daka_member_from_user(
            db,
            existing,
            register_channel=CHANNEL_WECHAT_LEGACY if snap else CHANNEL_WECHAT,
            openid=openid,
            unionid=unionid,
            legacy_matched=bool(snap),
            legacy_wx_member_id=snap.wx_member_id if snap else None,
        )
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
    register_daka_member_from_user(
        db,
        user,
        register_channel=CHANNEL_WECHAT_LEGACY if snap else CHANNEL_WECHAT,
        openid=openid,
        unionid=unionid,
        legacy_matched=bool(snap),
        legacy_wx_member_id=snap.wx_member_id if snap else None,
    )
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


BIND_SMS_MAX_PER_TICKET = 3


def _refresh_bind_ticket(ticket: str, row: dict) -> None:
    challenge_set(_bind_key(ticket), row, WX_BIND_TTL)


def assert_bind_ticket_sms_allowed(bind_ticket: str, phone: str) -> dict:
    """绑手机 SMS 限次 + 锁定手机号（B19）。"""
    from app.services.sms_service import normalize_phone

    row = get_bind_ticket(bind_ticket)
    sms_count = int(row.get("sms_count") or 0)
    if sms_count >= BIND_SMS_MAX_PER_TICKET:
        raise HTTPException(429, "该绑定会话验证码次数已达上限，请重新从微信进入")
    p = normalize_phone(phone)
    locked = (row.get("phone") or "").strip()
    if locked and locked != p:
        raise HTTPException(400, "请使用首次发送验证码的手机号")
    row["sms_count"] = sms_count + 1
    row["phone"] = p
    _refresh_bind_ticket(bind_ticket, row)
    return row


def create_bind_ticket(*, openid: str, unionid: str | None, wx_member_id: int | None) -> str:
    ticket = secrets.token_urlsafe(18)
    challenge_set(
        _bind_key(ticket),
        {
            "openid": openid,
            "unionid": unionid,
            "wx_member_id": wx_member_id,
            "sms_count": 0,
            "phone": "",
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


def create_login_exchange_ticket(*, user_id: int, next_step: str, role: str) -> str:
    ticket = secrets.token_urlsafe(18)
    challenge_set(
        _login_exchange_key(ticket),
        {"user_id": user_id, "next_step": next_step, "role": role},
        WX_LOGIN_EXCHANGE_TTL,
    )
    return ticket


def consume_login_exchange_ticket(ticket: str) -> dict:
    row = challenge_get(_login_exchange_key(ticket))
    if not row:
        raise HTTPException(400, "登录凭证已过期，请重新从微信进入")
    challenge_delete(_login_exchange_key(ticket))
    return row


def try_attach_openid_from_local_snapshot(db: Session, user: ChildUser) -> ChildUser:
    """保留供公司绑手机完成后调用；短信注册/登录不再自动绑 openid（须先走公司验证）。"""
    return user


def _try_link_user_from_local(
    db: Session,
    *,
    openid: str,
    unionid: str | None,
    snap: WxMemberSnapshot | None,
) -> tuple[ChildUser | None, str | None]:
    """本地 snapshot/daka_member 关联已注册家长；成功返回 (user, next_step)。"""
    from app.services.member_registry_service import (
        find_daka_member_by_legacy_wx_member_id,
        find_daka_member_by_mobile,
    )
    from app.services.parent_profile_service import parent_needs_company_verification

    oid = (openid or "").strip()
    if not oid:
        return None, None

    u_union = unionid or (snap.unionid if snap else None)
    mobile = _normalize_mobile(snap.mobile if snap else None) if snap else None

    if mobile:
        existing = auth_service.find_parent_by_phone_for_login(db, mobile)
        if not existing:
            dm = find_daka_member_by_mobile(db, mobile)
            if dm:
                existing = auth_service.get_parent_for_login(db, dm.parent_id)
        if existing:
            if parent_needs_company_verification(db, existing):
                return None, None
            step = finalize_wechat_login_user(
                db,
                existing,
                openid=oid,
                unionid=u_union,
                snap=snap,
            )
            return existing, step

    if snap and snap.wx_member_id:
        dm = find_daka_member_by_legacy_wx_member_id(db, snap.wx_member_id)
        if dm and dm.mobile:
            user = auth_service.get_parent_for_login(db, dm.parent_id)
            if not user:
                user = auth_service.find_parent_by_phone_for_login(db, dm.mobile)
            if user:
                if parent_needs_company_verification(db, user):
                    return None, None
                step = finalize_wechat_login_user(
                    db,
                    user,
                    openid=oid,
                    unionid=u_union,
                    snap=snap,
                )
                return user, step

    if snap and not mobile:
        rows = list(
            db.scalars(
                select(DakaMember).where(
                    DakaMember.openid.is_(None),
                    DakaMember.mobile.isnot(None),
                )
            )
        )
        for dm in rows:
            snap_by_phone = lookup_snapshot_by_mobile(db, dm.mobile)
            if not snap_by_phone or (snap_by_phone.openid or "").strip() != oid:
                continue
            user = auth_service.get_parent_for_login(db, dm.parent_id)
            if not user:
                user = auth_service.find_parent_by_phone_for_login(db, dm.mobile)
            if user:
                if parent_needs_company_verification(db, user):
                    return None, None
                step = finalize_wechat_login_user(
                    db,
                    user,
                    openid=oid,
                    unionid=u_union,
                    snap=snap_by_phone,
                )
                return user, step

    return None, None


def _provision_legacy_parent_from_snapshot(
    db: Session,
    *,
    openid: str,
    unionid: str | None,
    snap: WxMemberSnapshot,
) -> tuple[ChildUser | None, str | None]:
    """老库 snapshot 已有 openid+手机号、Jnao 无账号 → 自动建号绑定，免走公司验证页。"""
    from app.services.parent_profile_service import parent_needs_company_verification

    mobile = _normalize_mobile(snap.mobile)
    if not mobile:
        return None, None

    oid = (openid or "").strip()
    u_union = unionid or snap.unionid
    existing = auth_service.find_parent_by_phone_for_login(db, mobile)
    if existing:
        if parent_needs_company_verification(db, existing):
            return None, None
        step = finalize_wechat_login_user(
            db, existing, openid=oid, unionid=u_union, snap=snap
        )
        return existing, step

    user = ensure_parent_for_phone(
        db,
        phone=mobile,
        snap=snap,
        openid=oid,
        unionid=u_union,
    )
    step = finalize_wechat_login_user(
        db, user, openid=oid, unionid=u_union, snap=snap
    )
    logger.info(
        "legacy snapshot auto-provision user=%s phone=%s openid=%s…",
        user.id,
        mobile[-4:],
        oid[:10],
    )
    return user, step


def resolve_wechat_login(
    db: Session,
    *,
    openid: str,
    unionid: str | None,
) -> tuple[ChildUser | None, str | None, str]:
    """返回 (user, bind_ticket, next_step)。本地 snapshot/daka_member 优先，老库仅定时同步。"""
    from app.services.member_registry_service import find_daka_member_by_openid

    bind = get_bind_by_openid(db, openid)
    if bind:
        user = auth_service.get_parent_for_login(db, bind.parent_id)
        if user:
            snap = lookup_member_for_oauth(db, openid)
            step = finalize_wechat_login_user(
                db, user, openid=openid, unionid=unionid, snap=snap
            )
            return user, None, step
        db.delete(bind)
        db.commit()

    member = find_daka_member_by_openid(db, openid)
    if member:
        user = auth_service.get_parent_for_login(db, member.parent_id)
        if not user and member.mobile:
            user = auth_service.find_parent_by_phone_for_login(db, member.mobile)
            if user:
                member.parent_id = user.id
                db.flush()
        if user:
            snap = lookup_member_for_oauth(db, openid)
            step = finalize_wechat_login_user(
                db, user, openid=openid, unionid=unionid, snap=snap
            )
            return user, None, step
        member.openid = None
        db.flush()

    snap = lookup_member_local(db, openid)
    if not snap:
        ticket = create_bind_ticket(
            openid=openid,
            unionid=unionid,
            wx_member_id=None,
        )
        return None, ticket, "bind-phone"

    linked, step = _try_link_user_from_local(
        db, openid=openid, unionid=unionid, snap=snap
    )
    if linked and step:
        return linked, None, step

    mobile = snap.mobile
    if mobile:
        provisioned, step = _provision_legacy_parent_from_snapshot(
            db, openid=openid, unionid=unionid, snap=snap
        )
        if provisioned and step:
            return provisioned, None, step
        ticket = create_bind_ticket(
            openid=openid,
            unionid=unionid,
            wx_member_id=snap.wx_member_id if snap else None,
        )
        return None, ticket, "bind-phone"

    # 老库有 openid 但 snapshot 仍无手机号：走公司绑手机页
    if use_external_bind_mobile():
        ticket = create_bind_ticket(
            openid=openid,
            unionid=unionid,
            wx_member_id=snap.wx_member_id if snap else None,
        )
        return None, ticket, "bind-phone"

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
    existing = auth_service.find_parent_by_phone_for_login(db, phone)
    if existing:
        other = get_bind_by_parent(db, existing.id)
        if other and other.openid != openid:
            raise HTTPException(409, "该手机号已绑定其他微信账号")
    by_openid = get_bind_by_openid(db, openid)
    if by_openid and existing and by_openid.parent_id != existing.id:
        raise HTTPException(409, "该微信已绑定其他家长账号")
    snap = sync_snapshot_from_legacy(db, openid=openid, mobile=phone)
    user = ensure_parent_for_phone(
        db,
        phone=phone,
        snap=snap,
        openid=openid,
        unionid=pending.get("unionid"),
    )
    step = finalize_wechat_login_user(
        db,
        user,
        openid=openid,
        unionid=pending.get("unionid"),
        snap=snap,
    )
    logger.info("bind-phone complete user=%s openid=%s… step=%s", user.id, openid[:10], step)
    return user


def complete_external_bind_phone(db: Session, *, bind_ticket: str) -> ChildUser:
    """外链绑手机页返回后：强制从老库刷新 snapshot，再完成 openid+手机号绑定。"""
    from app.services.member_registry_service import find_daka_member_by_mobile, find_daka_member_by_openid

    pending = get_bind_ticket(bind_ticket)
    openid = pending["openid"]
    sync_snapshot_for_openid(db, openid)
    snap = lookup_member_local(db, openid)
    mobile = (snap.mobile if snap and snap.mobile else None)
    if not mobile:
        dm = find_daka_member_by_openid(db, openid)
        if dm and dm.mobile:
            mobile = dm.mobile
            snap = sync_snapshot_from_legacy(db, openid=openid, mobile=mobile)
    if not mobile:
        bind = get_bind_by_openid(db, openid)
        if bind:
            user = auth_service.get_parent_for_login(db, bind.parent_id)
            if user and user.parent_phone:
                mobile = user.parent_phone
    if not mobile:
        legacy = fetch_legacy_member(openid)
        if legacy and legacy.get("mobile"):
            mobile = legacy["mobile"]
            snap = sync_snapshot_from_legacy(db, openid=openid, mobile=mobile)
    if not mobile:
        raise HTTPException(400, "尚未完成手机号绑定，请先在绑手机页完成操作后再返回")
    user = complete_bind_phone(db, bind_ticket=bind_ticket, phone=mobile)
    # 公司页注册后：再按手机号对齐老库字段（openid 可能刚写入 ys_wx_member）
    legacy_by_phone = fetch_legacy_member_by_mobile(mobile)
    if legacy_by_phone:
        sync_snapshot_from_legacy(db, openid=openid, mobile=mobile)
        finalize_wechat_login_user(
            db,
            user,
            openid=legacy_by_phone.get("openid") or openid,
            unionid=legacy_by_phone.get("unionid") or pending.get("unionid"),
            snap=lookup_member_local(db, openid),
        )
    return user
