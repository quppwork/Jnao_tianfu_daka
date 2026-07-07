"""本平台家长会员注册表 — 与 wx_member_snapshot（老库镜像）分离"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, DakaMember
from app.services.sms_service import normalize_phone
from app.services.training_day import TZ

CHANNEL_SMS = "sms"
CHANNEL_PASSWORD = "password"
CHANNEL_WECHAT = "wechat"
CHANNEL_WECHAT_LEGACY = "wechat_legacy"


def find_daka_member_by_parent(db: Session, parent_id: int) -> DakaMember | None:
    return db.scalar(select(DakaMember).where(DakaMember.parent_id == parent_id))


def find_daka_member_by_mobile(db: Session, mobile: str) -> DakaMember | None:
    phone = normalize_phone(mobile)
    return db.scalar(select(DakaMember).where(DakaMember.mobile == phone))


def find_daka_member_by_openid(db: Session, openid: str) -> DakaMember | None:
    oid = (openid or "").strip()
    if not oid:
        return None
    return db.scalar(select(DakaMember).where(DakaMember.openid == oid))


def upsert_daka_member(
    db: Session,
    *,
    parent_id: int,
    mobile: str,
    register_channel: str,
    openid: str | None = None,
    unionid: str | None = None,
    legacy_matched: bool = False,
    legacy_wx_member_id: int | None = None,
    real_name: str | None = None,
    nickname: str | None = None,
) -> DakaMember:
    """注册或更新本平台会员记录（家长）。"""
    phone = normalize_phone(mobile)
    oid = (openid or "").strip() or None
    uid = (unionid or "").strip() or None
    channel = (register_channel or CHANNEL_SMS).strip()[:20]

    by_parent = find_daka_member_by_parent(db, parent_id)
    by_mobile = find_daka_member_by_mobile(db, phone)
    by_openid = find_daka_member_by_openid(db, oid) if oid else None

    if by_mobile and by_mobile.parent_id != parent_id:
        raise HTTPException(409, "该手机号已注册其他家长账号")
    if by_openid and by_openid.parent_id != parent_id:
        raise HTTPException(409, "该微信已绑定其他家长账号")

    now = datetime.now(TZ).replace(tzinfo=None)
    row = by_parent or by_mobile or by_openid
    if row:
        row.parent_id = parent_id
        row.mobile = phone
        if oid:
            row.openid = oid
        if uid:
            row.unionid = uid
        if legacy_matched:
            row.legacy_matched = 1
        if legacy_wx_member_id is not None:
            row.legacy_wx_member_id = legacy_wx_member_id
        if real_name and str(real_name).strip():
            row.real_name = str(real_name).strip()[:64]
        if nickname and str(nickname).strip():
            row.nickname = str(nickname).strip()[:50]
        row.updated_at = now
    else:
        row = DakaMember(
            parent_id=parent_id,
            mobile=phone,
            openid=oid,
            unionid=uid,
            register_channel=channel,
            legacy_matched=1 if legacy_matched else 0,
            legacy_wx_member_id=legacy_wx_member_id,
            real_name=(str(real_name).strip()[:64] if real_name else None),
            nickname=(str(nickname).strip()[:50] if nickname else None),
            registered_at=now,
            updated_at=now,
        )
        db.add(row)
    db.flush()
    return row


def register_daka_member_from_user(
    db: Session,
    user: ChildUser,
    *,
    register_channel: str,
    openid: str | None = None,
    unionid: str | None = None,
    legacy_matched: bool = False,
    legacy_wx_member_id: int | None = None,
) -> DakaMember:
    pj = user.profile_json or {}
    real_name = ((pj.get("parent") or {}).get("real_name") or "").strip() or None
    return upsert_daka_member(
        db,
        parent_id=user.id,
        mobile=user.parent_phone,
        register_channel=register_channel,
        openid=openid,
        unionid=unionid,
        legacy_matched=legacy_matched,
        legacy_wx_member_id=legacy_wx_member_id,
        real_name=real_name,
        nickname=user.nickname,
    )
