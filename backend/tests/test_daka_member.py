"""daka_member 本平台会员注册表"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from app.services import auth_service
from app.services.member_registry_service import (
    CHANNEL_SMS,
    register_daka_member_from_user,
    upsert_daka_member,
    find_daka_member_by_parent,
)


def test_sms_register_creates_daka_member(db_session: Session):
    from app.services.parent_profile_service import register_parent_by_sms

    user = register_parent_by_sms(
        db_session,
        phone="13900007777",
        nickname="新家长",
        real_name="王五",
        password="secret12",
    )
    row = find_daka_member_by_parent(db_session, user.id)
    assert row is not None
    assert row.mobile == "13900007777"
    assert row.register_channel == CHANNEL_SMS
    assert row.legacy_matched == 0


def test_wechat_legacy_match_creates_daka_member(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from app.services.wechat_auth_service import resolve_wechat_login, upsert_snapshot
    from app.services.member_registry_service import CHANNEL_WECHAT_LEGACY

    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 50,
            "openid": "oDAKA_legacy_050",
            "mobile": "13900008888",
            "nickname": "老会员",
            "truename": "赵六",
        },
    )
    db_session.commit()

    user, ticket, step = resolve_wechat_login(db_session, openid="oDAKA_legacy_050", unionid=None)
    assert user is not None
    assert ticket is None

    row = find_daka_member_by_parent(db_session, user.id)
    assert row is not None
    assert row.openid == "oDAKA_legacy_050"
    assert row.register_channel == CHANNEL_WECHAT_LEGACY
    assert row.legacy_matched == 1
    assert row.legacy_wx_member_id == 50


def test_daka_member_openid_login_without_snapshot(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from app.services.wechat_auth_service import resolve_wechat_login
    from app.services.parent_profile_service import mark_phone_verified, set_login_channel, LOGIN_CHANNEL_WECHAT

    parent = auth_service.register_child(
        db_session,
        parent_phone="13900009999",
        nickname="已注册",
        role=auth_service.ROLE_PARENT,
    )
    set_login_channel(parent, LOGIN_CHANNEL_WECHAT)
    mark_phone_verified(parent)
    upsert_daka_member(
        db_session,
        parent_id=parent.id,
        mobile="13900009999",
        register_channel=CHANNEL_SMS,
        openid="oDAKA_existing_099",
    )
    db_session.commit()

    user, ticket, step = resolve_wechat_login(db_session, openid="oDAKA_existing_099", unionid=None)
    assert user is not None
    assert user.id == parent.id
    assert ticket is None
    assert step in ("complete-profile", "home", "bind-phone")
