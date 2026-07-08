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
from app.services.wechat_auth_service import upsert_snapshot, resolve_wechat_login, upsert_wechat_bind


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
    assert user is None
    assert ticket is not None
    assert step == "bind-phone"


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


def test_resolve_wechat_login_unknown_openid(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: None)
    user, ticket, step = resolve_wechat_login(db_session, openid="oUNKNOWN_not_in_snapshot", unionid=None)
    assert user is None
    assert ticket is None
    assert step == "register"


def test_oauth_lazy_load_legacy_when_missing_local(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")

    def fake_fetch(openid: str):
        if openid == "oLAZY_001":
            return {
                "wx_member_id": 9001,
                "openid": openid,
                "unionid": None,
                "mobile": "13900001234",
                "nickname": "懒加载",
                "truename": "测试",
            }
        return None

    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: object())
    monkeypatch.setattr("app.services.wechat_auth_service.fetch_legacy_member", fake_fetch)

    user, ticket, step = resolve_wechat_login(db_session, openid="oLAZY_001", unionid=None)
    assert user is None
    assert ticket is not None
    assert step == "bind-phone"

    from app.services.wechat_auth_service import lookup_member_local

    snap = lookup_member_local(db_session, "oLAZY_001")
    assert snap is not None
    assert snap.mobile == "13900001234"


def test_oauth_lazy_refresh_mobile_when_local_empty(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 9002,
            "openid": "oLAZY_002",
            "mobile": None,
            "nickname": "无手机",
        },
    )
    db_session.commit()

    def fake_fetch(openid: str):
        if openid == "oLAZY_002":
            return {
                "wx_member_id": 9002,
                "openid": openid,
                "mobile": "13900005678",
                "nickname": "已绑手机",
            }
        return None

    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: object())
    monkeypatch.setattr("app.services.wechat_auth_service.fetch_legacy_member", fake_fetch)

    user, ticket, step = resolve_wechat_login(db_session, openid="oLAZY_002", unionid=None)
    assert user is None
    assert ticket is not None
    assert step == "bind-phone"


def test_sync_wx_members_from_legacy(db_session: Session, monkeypatch):
    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "id": 100,
                    "openid": "oSYNC_001",
                    "unionid": "u100",
                    "mobile": "13900006666",
                    "nickname": "同步测试",
                    "truename": "张三",
                },
                {
                    "id": 101,
                    "openid": "oSYNC_002",
                    "unionid": None,
                    "mobile": "",
                    "nickname": "无手机",
                    "truename": None,
                },
            ]

    class FakeConn:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConn()

    monkeypatch.setattr(
        "app.services.wechat_auth_service.get_legacy_engine",
        lambda: FakeEngine(),
    )
    from app.services.wechat_auth_service import sync_wx_members_from_legacy

    stats = sync_wx_members_from_legacy(db_session)
    assert stats["total"] == 2
    assert stats["with_mobile"] == 1
    assert stats["without_mobile"] == 1
    assert stats["mode"] == "full"


def test_sync_wx_members_incremental_by_id(db_session: Session, monkeypatch):
    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 100,
            "openid": "oINC_100",
            "mobile": "13900001000",
        },
    )
    db_session.commit()

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class FakeConn:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "id >" in sql:
                assert params["last_id"] == 100
                return FakeResult([
                    {
                        "id": 101,
                        "openid": "oINC_101",
                        "unionid": None,
                        "mobile": "13900001001",
                        "nickname": "新会员",
                        "truename": None,
                    }
                ])
            return FakeResult([])

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConn()

    monkeypatch.setattr(
        "app.services.wechat_auth_service.get_legacy_engine",
        lambda: FakeEngine(),
    )
    monkeypatch.setattr(
        "app.services.wechat_auth_service._pick_legacy_time_column",
        lambda _engine: None,
    )
    monkeypatch.setattr(
        "app.services.wechat_auth_service._load_sync_state",
        lambda: {"last_id": 100},
    )
    saved = {}

    def fake_save(state):
        saved.update(state)

    monkeypatch.setattr("app.services.wechat_auth_service._save_sync_state", fake_save)

    from app.services.wechat_auth_service import sync_wx_members_incremental

    stats = sync_wx_members_incremental(db_session)
    assert stats["total"] == 1
    assert stats["mode"] == "id"
    assert saved.get("last_id") == 101


def test_external_bind_mobile_url_with_ticket(monkeypatch):
    monkeypatch.delenv("WECHAT_BIND_MOBILE_URL", raising=False)
    from app.services.wechat_auth_service import build_external_bind_mobile_url

    url = build_external_bind_mobile_url(bind_ticket="test-ticket-abc")
    assert "m.jnao.com" in url
    assert "bind_ticket" in url
    assert "test-ticket-abc" in url


def test_upsert_wechat_bind_rejects_openid_conflict(db_session: Session, monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from fastapi import HTTPException

    u1 = auth_service.register_child(
        db_session,
        parent_phone="13900004444",
        nickname="家长A",
        role=auth_service.ROLE_PARENT,
    )
    u2 = auth_service.register_child(
        db_session,
        parent_phone="13900005555",
        nickname="家长B",
        role=auth_service.ROLE_PARENT,
    )
    db_session.commit()

    upsert_wechat_bind(
        db_session,
        parent_id=u1.id,
        openid="oCONFLICT_001",
        unionid=None,
        wx_member_id=1,
    )
    db_session.commit()

    try:
        upsert_wechat_bind(
            db_session,
            parent_id=u2.id,
            openid="oCONFLICT_001",
            unionid=None,
            wx_member_id=1,
        )
        assert False, "expected 409"
    except HTTPException as e:
        assert e.status_code == 409


def test_login_exchange_ticket_one_time(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from app.services.wechat_auth_service import (
        create_login_exchange_ticket,
        consume_login_exchange_ticket,
    )

    ticket = create_login_exchange_ticket(user_id=99, next_step="home", role="parent")
    row = consume_login_exchange_ticket(ticket)
    assert row["user_id"] == 99
    assert row["next_step"] == "home"

    from fastapi import HTTPException

    try:
        consume_login_exchange_ticket(ticket)
        assert False, "expected expired"
    except HTTPException as e:
        assert e.status_code == 400
