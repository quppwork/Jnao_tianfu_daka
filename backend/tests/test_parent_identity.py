"""家长身份解析 — 防重复注册"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.models import WxMemberSnapshot
from app.services import auth_service
from app.services.parent_identity_service import (
    ACTION_LOGIN,
    ACTION_REGISTER,
    ACTION_WECHAT_LOGIN,
    assert_parent_can_register,
    resolve_parent_registration_state,
)


def test_resolve_none(db_session):
    st = resolve_parent_registration_state(db_session, "13900009901")
    assert st["registered"] is False
    assert st["action"] == ACTION_REGISTER


def test_resolve_child_user(db_session):
    auth_service.register_child(
        db_session,
        parent_phone="13900009902",
        nickname="家长A",
        role=auth_service.ROLE_PARENT,
        child_quota=5,
    )
    st = resolve_parent_registration_state(db_session, "13900009902")
    assert st["registered"] is True
    assert st["action"] == ACTION_LOGIN


def test_resolve_wx_snapshot_blocks_register(db_session):
    db_session.add(
        WxMemberSnapshot(
            openid="o_test_snapshot_1",
            mobile="13900009903",
            nickname="老用户",
        )
    )
    db_session.commit()
    st = resolve_parent_registration_state(db_session, "13900009903")
    assert st["registered"] is True
    assert st["action"] == ACTION_WECHAT_LOGIN
    with pytest.raises(HTTPException) as exc:
        assert_parent_can_register(db_session, "13900009903")
    assert exc.value.status_code == 409


class TestParentIdentityApi:
    def test_phone_check_enhanced(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_api_snap", mobile="13900009904", nickname="镜像")
        )
        db_session.commit()
        res = client.get("/api/auth/parent/phone-check", params={"phone": "13900009904"})
        assert res.status_code == 200
        data = res.json()
        assert data["registered"] is True
        assert data["action"] == ACTION_WECHAT_LOGIN

    def test_register_sms_blocked_by_snapshot(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_reg_block", mobile="13900009905", nickname="镜像")
        )
        db_session.commit()
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900009905",
                "scene": "register",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 409

    def test_login_sms_blocked_by_snapshot_only(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_login_block", mobile="13900009906", nickname="镜像")
        )
        db_session.commit()
        res = client.post(
            "/api/auth/sms/send",
            json={"phone": "13900009906", "scene": "login"},
        )
        assert res.status_code == 404
        assert "微信" in res.json()["detail"]
