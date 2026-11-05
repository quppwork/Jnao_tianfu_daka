"""短信验证码登录/注册测试"""

import pytest
from fastapi.testclient import TestClient

SMS_OK = "若号码有效，验证码已发送"


@pytest.fixture(autouse=True)
def _auth_mock_env(monkeypatch):
    monkeypatch.setenv("AUTH_CHALLENGE_MOCK", "1")
    monkeypatch.setenv("SMS_PROVIDER", "mock")
    monkeypatch.setenv("SMS_MOCK_CODE", "88888")


def _send_register_sms(client: TestClient, phone: str) -> None:
    cap = client.get("/api/auth/captcha")
    cid = cap.json()["captcha_id"]
    res = client.post(
        "/api/auth/sms/send",
        json={
            "phone": phone,
            "scene": "register",
            "captcha_id": cid,
            "captcha_code": "0000",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["message"] == SMS_OK


def _send_login_sms(client: TestClient, phone: str) -> None:
    cap = client.get("/api/auth/captcha")
    cid = cap.json()["captcha_id"]
    res = client.post(
        "/api/auth/sms/send",
        json={
            "phone": phone,
            "scene": "login",
            "captcha_id": cid,
            "captcha_code": "0000",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["message"] == SMS_OK
    assert data["sent"] is True


class TestSmsAuth:
    def test_register_flow(self, client: TestClient):
        phone = "13900008811"
        _send_register_sms(client, phone)
        res = client.post(
            "/api/auth/sms/register",
            json={
                "phone": phone,
                "sms_code": "88888",
                "real_name": "张家长",
                "nickname": "张妈妈",
                "password": "Zhang123A",
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["role"] == "parent"
        assert data["profile_complete"] is True

    def test_register_with_password_then_login(self, client: TestClient):
        phone = "13900008816"
        _send_register_sms(client, phone)
        reg = client.post(
            "/api/auth/sms/register",
            json={
                "phone": phone,
                "sms_code": "88888",
                "real_name": "李家长",
                "nickname": "李妈妈",
                "password": "Zhang123A",
            },
        )
        assert reg.status_code == 200, reg.text
        login = client.post(
            "/api/auth/login",
            json={"parent_phone": phone, "password": "Zhang123A", "role": "parent"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["child_user_id"] == reg.json()["child_user_id"]

    def test_register_rejects_weak_password(self, client: TestClient):
        phone = "13900008819"
        _send_register_sms(client, phone)
        reg = client.post(
            "/api/auth/sms/register",
            json={
                "phone": phone,
                "sms_code": "88888",
                "real_name": "弱口令",
                "nickname": "家长",
                "password": "12345678",
            },
        )
        assert reg.status_code == 400

    def test_login_sms_unregistered_phone_unified_response(self, client: TestClient):
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900008812",
                "scene": "login",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == SMS_OK
        assert data["sent"] is False
        assert data["hint"] == "not_registered"

    def test_login_sms_unregistered_does_not_store_code(self, client: TestClient):
        from app.services.auth_challenge_store import challenge_get
        from app.services.sms_service import SCENE_LOGIN, _sms_key

        phone = "13900008812"
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": phone,
                "scene": "login",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        assert res.json()["sent"] is False
        assert challenge_get(_sms_key(SCENE_LOGIN, phone)) is None

    def test_login_sms_registered_sends_code(self, client: TestClient, db_session):
        from app.services.auth_challenge_store import challenge_get
        from app.services.auth_service import register_child, ROLE_PARENT
        from app.services.sms_service import SCENE_LOGIN, _sms_key

        phone = "13900008819"
        register_child(
            db_session,
            parent_phone=phone,
            nickname="验证码家长",
            password=None,
            role=ROLE_PARENT,
            child_quota=5,
        )
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": phone,
                "scene": "login",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["sent"] is True
        assert data.get("hint") is None
        assert challenge_get(_sms_key(SCENE_LOGIN, phone)) is not None

    def test_login_sms_existing_parent(self, client: TestClient, db_session):
        from app.services.auth_service import register_child, ROLE_PARENT

        register_child(
            db_session,
            parent_phone="13900008813",
            nickname="老家长",
            password=None,
            role=ROLE_PARENT,
            child_quota=5,
        )
        _send_login_sms(client, "13900008813")
        res = client.post(
            "/api/auth/sms/login",
            json={"phone": "13900008813", "sms_code": "88888"},
        )
        assert res.status_code == 200
        assert res.json()["nickname"] == "老家长"

    def test_register_requires_captcha(self, client: TestClient):
        res = client.post(
            "/api/auth/sms/send",
            json={"phone": "13900008814", "scene": "register"},
        )
        assert res.status_code == 400

    def test_register_duplicate_phone_unified_sms(self, client: TestClient, db_session):
        from app.services.auth_service import register_child, ROLE_PARENT

        register_child(
            db_session,
            parent_phone="13900008815",
            nickname="已存在",
            role=ROLE_PARENT,
            child_quota=5,
        )
        cap = client.get("/api/auth/captcha")
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900008815",
                "scene": "register",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == SMS_OK
        assert data["sent"] is False
        assert data["hint"] == "already_registered"
        from app.db.models import WxMemberSnapshot

        db_session.add(
            WxMemberSnapshot(openid="o_dup_test", mobile="13900008817", nickname="老")
        )
        db_session.commit()
        _send_register_sms(client, "13900008817")
        res = client.post(
            "/api/auth/sms/register",
            json={
                "phone": "13900008817",
                "sms_code": "88888",
                "real_name": "王家长",
                "nickname": "王妈妈",
                "password": "Zhang123A",
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["role"] == "parent"

    def test_sms_login_rejects_unregistered(self, client: TestClient):
        res = client.post(
            "/api/auth/sms/login",
            json={"phone": "13900008899", "sms_code": "88888"},
        )
        assert res.status_code == 404
        assert "尚未注册" in res.json()["detail"]

    def test_password_login_unregistered_returns_404(self, client: TestClient):
        res = client.post(
            "/api/auth/login",
            json={
                "parent_phone": "13900008898",
                "password": "Zhang123A",
                "role": "parent",
            },
        )
        assert res.status_code == 404
        assert "尚未注册" in res.json()["detail"]

    def test_login_sms_requires_captcha(self, client: TestClient, db_session):
        from app.services.auth_service import register_child, ROLE_PARENT

        register_child(
            db_session,
            parent_phone="13900008818",
            nickname="需验证码",
            role=ROLE_PARENT,
            child_quota=5,
        )
        res = client.post(
            "/api/auth/sms/send",
            json={"phone": "13900008818", "scene": "login"},
        )
        assert res.status_code == 400
        assert "图形验证" in res.json()["detail"]

    def test_captcha_returns_png_format(self, client: TestClient):
        res = client.get("/api/auth/captcha")
        assert res.status_code == 200
        data = res.json()
        assert data["image_format"] == "png"
        assert "image_base64" in data

    def test_admin_blacklist_unban(self, client: TestClient, db_session):
        from app.services.blacklist_service import add_blacklist_entry

        admin = client.post(
            "/api/admin/login",
            json={"login_name": "pyx", "password": "123456"},
        ).json()
        auth = {
            "params": {"user_id": admin["child_user_id"]},
            "headers": {
                "X-Child-User-Id": str(admin["child_user_id"]),
                "X-Session-Token": admin["session_token"],
            },
        }
        add_blacklist_entry(db_session, "ip", "203.0.113.99", reason="test")
        lst = client.get("/api/admin/blacklist", **auth)
        assert lst.status_code == 200
        assert any(r["value"] == "203.0.113.99" for r in lst.json()["ips"])
        rm = client.delete("/api/admin/blacklist/ip/203.0.113.99", **auth)
        assert rm.status_code == 200
