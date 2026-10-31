"""家长身份解析 — 防重复注册"""

from fastapi.testclient import TestClient

from app.db.models import WxMemberSnapshot
from app.services import auth_service
from app.services.parent_identity_service import (
    ACTION_LOGIN,
    ACTION_REGISTER,
    assert_parent_can_register,
    resolve_parent_registration_state,
)


def _send_register_sms(client: TestClient, phone: str) -> None:
    cap = client.get("/api/auth/captcha")
    res = client.post(
        "/api/auth/sms/send",
        json={
            "phone": phone,
            "scene": "register",
            "captcha_id": cap.json()["captcha_id"],
            "captcha_code": "0000",
        },
    )
    assert res.status_code == 200, res.text


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


def test_resolve_wx_snapshot_allows_register(db_session):
    db_session.add(
        WxMemberSnapshot(
            openid="o_test_snapshot_1",
            mobile="13900009903",
            nickname="老用户",
        )
    )
    db_session.commit()
    st = resolve_parent_registration_state(db_session, "13900009903")
    assert st["registered"] is False
    assert st["action"] == ACTION_REGISTER
    assert_parent_can_register(db_session, "13900009903")


class TestParentIdentityApi:
    def test_phone_check_unified_response(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_api_snap", mobile="13900009904", nickname="镜像")
        )
        db_session.commit()
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/parent/phone-check",
            json={
                "phone": "13900009904",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert "registered" not in data
        assert "action" not in data

    def test_phone_check_requires_captcha(self, client: TestClient):
        res = client.post(
            "/api/auth/parent/phone-check",
            json={"phone": "13900009999"},
        )
        assert res.status_code in (400, 422)

    def test_register_sms_allowed_with_snapshot_only(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_reg_block", mobile="13900009905", nickname="镜像")
        )
        db_session.commit()
        _send_register_sms(client, "13900009905")
        res = client.post(
            "/api/auth/sms/register",
            json={
                "phone": "13900009905",
                "sms_code": "88888",
                "real_name": "新家长",
                "nickname": "新家长",
                "password": "Zhang123A",
            },
        )
        assert res.status_code == 200
        assert res.json()["role"] == "parent"

    def test_login_sms_unregistered_unified(self, client: TestClient, db_session):
        db_session.add(
            WxMemberSnapshot(openid="o_login_block", mobile="13900009906", nickname="镜像")
        )
        db_session.commit()
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900009906",
                "scene": "login",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        assert res.json()["message"] == "若号码有效，验证码已发送"
