"""微信家长 account_ready 与 snapshot 逻辑"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ChildUser, WxMemberSnapshot
from app.services import auth_service
from app.services.parent_profile_service import (
    LOGIN_CHANNEL_WECHAT,
    parent_account_ready,
    parent_next_step,
    parent_wechat_missing_fields,
    set_login_channel,
)
from app.services.wechat_auth_service import upsert_snapshot, resolve_wechat_login


def test_wechat_parent_missing_password(db_session: Session):
    user = auth_service.register_child(
        db_session,
        parent_phone="13900001111",
        nickname="微信家长",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
    )
    set_login_channel(user, LOGIN_CHANNEL_WECHAT)
    user.profile_json = {
        "parent": {
            "real_name": "张三",
            "phone_verified_at": "2026-07-07 12:00:00",
            "login_channel": LOGIN_CHANNEL_WECHAT,
        }
    }
    db_session.commit()
    db_session.refresh(user)

    missing = parent_wechat_missing_fields(user)
    assert "password" in missing
    assert not parent_account_ready(user)
    assert parent_next_step(user) == "complete-profile"


def test_wechat_parent_account_ready_with_password(db_session: Session):
    from app.core.password import hash_password

    user = auth_service.register_child(
        db_session,
        parent_phone="13900002222",
        nickname="完整家长",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="secret12",
    )
    set_login_channel(user, LOGIN_CHANNEL_WECHAT)
    user.profile_json = {
        "parent": {
            "real_name": "李四",
            "phone_verified_at": "2026-07-07 12:00:00",
            "login_channel": LOGIN_CHANNEL_WECHAT,
        }
    }
    user.password_hash = hash_password("secret12")
    db_session.commit()
    db_session.refresh(user)

    assert parent_account_ready(user)
    assert parent_next_step(user) == "home"


def test_resolve_wechat_login_with_mobile_snapshot(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 1,
            "openid": "oTEST_mobile_001",
            "unionid": "u001",
            "mobile": "13900003333",
            "nickname": "测试",
            "truename": "测试家长",
        },
    )
    db_session.commit()

    user, ticket, step = resolve_wechat_login(db_session, openid="oTEST_mobile_001", unionid="u001")
    assert user is not None
    assert ticket is None
    assert step in ("complete-profile", "home")
    assert user.parent_phone == "13900003333"


def test_resolve_wechat_login_without_mobile(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_BIND_MOBILE_URL", "")
    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 2,
            "openid": "oTEST_nomobile_002",
            "mobile": None,
            "nickname": "无手机",
        },
    )
    db_session.commit()

    user, ticket, step = resolve_wechat_login(db_session, openid="oTEST_nomobile_002", unionid=None)
    assert user is None
    assert ticket
    assert step == "bind-phone"


def test_external_bind_mobile_url_default(monkeypatch):
    monkeypatch.delenv("WECHAT_BIND_MOBILE_URL", raising=False)
    from app.services.wechat_auth_service import build_external_bind_mobile_url

    url = build_external_bind_mobile_url()
    assert "m.jnao.com" in url
    assert "bindmobile" in url
