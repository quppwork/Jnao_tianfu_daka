"""短信验证码登录/注册测试"""

import pytest
from fastapi.testclient import TestClient


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
                "password": "123456",
            },
        )
        assert reg.status_code == 200, reg.text
        login = client.post(
            "/api/auth/login",
            json={"parent_phone": phone, "password": "123456", "role": "parent"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["child_user_id"] == reg.json()["child_user_id"]

    def test_login_sms_unregistered_phone(self, client: TestClient):
        res = client.post(
            "/api/auth/sms/send",
            json={"phone": "13900008812", "scene": "login"},
        )
        assert res.status_code == 404

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

    def test_register_duplicate_phone(self, client: TestClient, db_session):
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
        assert res.status_code == 409

    def test_register_rejected_after_snapshot(self, client: TestClient, db_session):
        from app.db.models import WxMemberSnapshot

        db_session.add(
            WxMemberSnapshot(openid="o_dup_test", mobile="13900008817", nickname="老")
        )
        db_session.commit()
        cap = client.get("/api/auth/captcha")
        send = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900008817",
                "scene": "register",
                "captcha_id": cap.json()["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert send.status_code == 409

    def test_sms_login_rejects_unregistered(self, client: TestClient):
        res = client.post(
            "/api/auth/sms/login",
            json={"phone": "13900008899", "sms_code": "88888"},
        )
        assert res.status_code == 400

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
