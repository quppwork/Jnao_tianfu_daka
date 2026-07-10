"""微信家长 account_ready 与 snapshot 逻辑"""

from __future__ import annotations

from sqlalchemy import select
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
    """snapshot 有手机号、Jnao 无账号 → 老用户自动建号。"""
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
    assert user.parent_phone == "13900003333"
    assert ticket is None
    assert step in ("home", "complete-profile")


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
    monkeypatch.setenv("WECHAT_BIND_MOBILE_URL", "https://m.jnao.com/home/member/bindmobile.html")
    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: None)
    user, ticket, step = resolve_wechat_login(db_session, openid="oUNKNOWN_not_in_snapshot", unionid=None)
    assert user is None
    assert ticket is not None
    assert step == "bind-phone"


def test_oauth_local_only_no_lazy_legacy(db_session: Session, monkeypatch):
    """OAuth 不懒查老库；缺本地 snapshot 时走公司绑手机。"""
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")

    def fail_fetch(_openid: str):
        raise AssertionError("OAuth must not fetch legacy DB")

    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: object())
    monkeypatch.setattr("app.services.wechat_auth_service.fetch_legacy_member", fail_fetch)

    user, ticket, step = resolve_wechat_login(db_session, openid="oLAZY_001", unionid=None)
    assert user is None
    assert ticket is not None
    assert step == "bind-phone"


def test_oauth_local_snapshot_no_mobile_stays_bind_phone(db_session: Session, monkeypatch):
    """本地 snapshot 有 openid 无手机号、且 Jnao 无对应家长 → 走 bind-phone，不查老库。"""
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

    def fail_fetch(_openid: str):
        raise AssertionError("OAuth must not fetch legacy DB")

    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: object())
    monkeypatch.setattr("app.services.wechat_auth_service.fetch_legacy_member", fail_fetch)

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


def test_login_exchange_ticket_idempotent_retry(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from app.services.auth_challenge_store import challenge_delete
    from app.services.wechat_auth_service import (
        _login_exchange_used_key,
        create_login_exchange_ticket,
        consume_login_exchange_ticket,
    )

    ticket = create_login_exchange_ticket(user_id=99, next_step="home", role="parent")
    row = consume_login_exchange_ticket(ticket)
    assert row["user_id"] == 99
    assert row["next_step"] == "home"

    row2 = consume_login_exchange_ticket(ticket)
    assert row2["user_id"] == 99

    challenge_delete(_login_exchange_used_key(ticket))
    from fastapi import HTTPException

    try:
        consume_login_exchange_ticket(ticket)
        assert False, "expected expired"
    except HTTPException as e:
        assert e.status_code == 400


def test_resolve_wechat_login_links_sms_registered_parent(db_session: Session, monkeypatch):
    """snapshot 有手机号 + Jnao 短信注册无 openid → 须走公司绑手机，不直接登录。"""
    from app.core.password import hash_password
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user

    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    user = auth_service.register_child(
        db_session,
        parent_phone="15309546393",
        nickname="pyx",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {
        "parent": {
            "real_name": "彭",
            "phone_verified_at": "2026-07-07 12:00:00",
        }
    }
    register_daka_member_from_user(db_session, user, register_channel=CHANNEL_SMS)
    db_session.commit()

    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 8801,
            "openid": "oSMS_link_test",
            "mobile": "15309546393",
            "truename": "彭",
        },
    )
    db_session.commit()

    linked, ticket, step = resolve_wechat_login(
        db_session, openid="oSMS_link_test", unionid=None
    )
    assert linked is None
    assert ticket is not None
    assert step == "bind-phone"


def test_resolve_wechat_login_bound_parent_not_bind_phone(db_session: Session, monkeypatch):
    """已绑定微信且 daka_member 有手机号，缺 phone_verified 标记也不应走 bind-phone。"""
    from app.core.password import hash_password
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user

    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    user = auth_service.register_child(
        db_session,
        parent_phone="13900007777",
        nickname="已注册",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {"parent": {"real_name": "王", "login_channel": LOGIN_CHANNEL_WECHAT}}
    register_daka_member_from_user(db_session, user, register_channel=CHANNEL_SMS)
    upsert_wechat_bind(
        db_session,
        parent_id=user.id,
        openid="oBOUND_no_verify",
        unionid=None,
        wx_member_id=None,
    )
    db_session.commit()

    linked, ticket, step = resolve_wechat_login(
        db_session, openid="oBOUND_no_verify", unionid=None
    )
    assert linked is not None
    assert ticket is None
    assert step != "bind-phone"


def test_resolve_links_sms_parent_via_legacy_wx_member_id(db_session: Session, monkeypatch):
    """短信注册无 openid，即使 legacy_wx_member_id 对齐也须走公司绑手机。"""
    from app.core.password import hash_password
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user

    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    user = auth_service.register_child(
        db_session,
        parent_phone="19805031756",
        nickname="qupp",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {
        "parent": {
            "real_name": "测试",
            "phone_verified_at": "2026-07-10 12:00:00",
        }
    }
    register_daka_member_from_user(
        db_session,
        user,
        register_channel=CHANNEL_SMS,
        legacy_wx_member_id=1001,
        legacy_matched=True,
    )
    db_session.commit()

    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 1001,
            "openid": "oLEGACY_198",
            "mobile": None,
            "nickname": "qupp",
            "truename": "测试",
        },
    )
    db_session.commit()

    linked, ticket, step = resolve_wechat_login(
        db_session, openid="oLEGACY_198", unionid=None
    )
    assert linked is None
    assert ticket is not None
    assert step == "bind-phone"


def test_sms_login_requires_company_verification(db_session: Session, monkeypatch):
    """浏览器短信注册无 openid → gate 未通过，写操作应被拦截。"""
    from app.core.password import hash_password
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user
    from app.services.parent_profile_service import (
        parent_gate_passed,
        parent_needs_company_verification,
    )

    user = auth_service.register_child(
        db_session,
        parent_phone="13900006601",
        nickname="待验证",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {
        "parent": {"real_name": "待验证", "phone_verified_at": "2026-07-10 12:00:00"}
    }
    register_daka_member_from_user(db_session, user, register_channel=CHANNEL_SMS)
    db_session.commit()

    assert parent_needs_company_verification(db_session, user) is True
    assert parent_gate_passed(db_session, user) is False


def test_finalize_wechat_sets_gate_passed(db_session: Session, monkeypatch):
    """微信绑定完成后写入 wechat_bound_at。"""
    from app.core.password import hash_password
    from app.services.member_registry_service import CHANNEL_SMS, find_daka_member_by_parent, register_daka_member_from_user
    from app.services.parent_profile_service import parent_gate_passed
    from app.services.wechat_auth_service import finalize_wechat_login_user, upsert_snapshot

    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    user = auth_service.register_child(
        db_session,
        parent_phone="13900006602",
        nickname="老用户",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {
        "parent": {"real_name": "老", "phone_verified_at": "2026-07-10 12:00:00"}
    }
    register_daka_member_from_user(
        db_session,
        user,
        register_channel=CHANNEL_SMS,
        legacy_wx_member_id=2001,
        legacy_matched=True,
    )
    snap = upsert_snapshot(
        db_session,
        {
            "wx_member_id": 2001,
            "openid": "oGATE_pass_01",
            "mobile": "13900006602",
            "truename": "老",
        },
    )
    db_session.commit()

    finalize_wechat_login_user(
        db_session, user, openid="oGATE_pass_01", unionid=None, snap=snap
    )
    dm = find_daka_member_by_parent(db_session, user.id)
    assert dm.wechat_bound_at is not None
    assert dm.company_verified_at is not None
    assert parent_gate_passed(db_session, user) is True


def test_legacy_snapshot_auto_provision_like_19805031756(db_session: Session, monkeypatch):
    """模拟 19805031756：老库 snapshot 齐全、Jnao 无账号 → 微信直达。"""
    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    from app.db.models import ParentWechatBind
    from app.services.member_registry_service import find_daka_member_by_parent
    from sqlalchemy import select

    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 57231,
            "openid": "o830W6_legacy_57231",
            "unionid": "u57231",
            "mobile": "19805031756",
            "nickname": "自在",
            "truename": None,
        },
    )
    db_session.commit()

    user, ticket, step = resolve_wechat_login(
        db_session, openid="o830W6_legacy_57231", unionid="u57231"
    )
    assert user is not None
    assert user.parent_phone == "19805031756"
    assert ticket is None
    assert step in ("home", "complete-profile")

    dm = find_daka_member_by_parent(db_session, user.id)
    assert dm.openid == "o830W6_legacy_57231"
    assert dm.wechat_bound_at is not None

    bind = db_session.scalar(
        select(ParentWechatBind).where(ParentWechatBind.parent_id == user.id)
    )
    assert bind is not None
    assert bind.openid == "o830W6_legacy_57231"


def test_sms_login_does_not_auto_attach_openid(db_session: Session, monkeypatch):
    """短信登录不再自动绑定 snapshot openid（须先走公司验证）。"""
    from app.core.password import hash_password
    from app.db.models import ParentWechatBind
    from app.services.member_registry_service import CHANNEL_SMS, register_daka_member_from_user
    from app.services.parent_profile_service import login_parent_by_sms

    monkeypatch.setenv("WECHAT_MP_APP_ID", "wx_test_app")
    user = auth_service.register_child(
        db_session,
        parent_phone="13900008888",
        nickname="自动绑",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
        password="Zhang123A",
    )
    user.password_hash = hash_password("Zhang123A")
    user.profile_json = {
        "parent": {
            "real_name": "自动绑",
            "phone_verified_at": "2026-07-10 12:00:00",
        }
    }
    register_daka_member_from_user(db_session, user, register_channel=CHANNEL_SMS)
    db_session.commit()

    upsert_snapshot(
        db_session,
        {
            "wx_member_id": 8802,
            "openid": "oSMS_attach_reg",
            "mobile": "13900008888",
            "truename": "自动绑",
        },
    )
    db_session.commit()

    login_parent_by_sms(db_session, phone="13900008888")
    bind = db_session.scalar(
        select(ParentWechatBind).where(ParentWechatBind.parent_id == user.id)
    )
    assert bind is None


def test_fetch_legacy_member_by_mobile_mock(monkeypatch):
    monkeypatch.setattr("app.services.wechat_auth_service.get_legacy_engine", lambda: object())

    def fake_mobile(mobile: str):
        if mobile == "19805031756":
            return {
                "wx_member_id": 1001,
                "openid": "oLEGACY_198",
                "unionid": None,
                "mobile": "19805031756",
                "nickname": "qupp",
                "truename": "测试",
            }
        return None

    monkeypatch.setattr(
        "app.services.wechat_auth_service.fetch_legacy_member_by_mobile",
        fake_mobile,
    )
    from app.services.wechat_auth_service import fetch_legacy_member_by_mobile

    row = fetch_legacy_member_by_mobile("19805031756")
    assert row is not None
    assert row["openid"] == "oLEGACY_198"
    assert row["mobile"] == "19805031756"
