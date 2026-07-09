"""家长/孩子账号体系 — 短信验证码注册 + 密码登录"""

import pytest
from fastapi.testclient import TestClient


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


def _register_parent(
    client: TestClient,
    phone: str = "13900001111",
    password: str = "123456",
    *,
    nickname: str = "张家长",
) -> dict:
    _send_register_sms(client, phone)
    res = client.post(
        "/api/auth/sms/register",
        json={
            "phone": phone,
            "sms_code": "88888",
            "real_name": "张三",
            "nickname": nickname,
            "password": password,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _parent_auth(parent: dict) -> dict:
    return {
        "params": {
            "user_id": parent["child_user_id"],
            "session_token": parent.get("session_token", ""),
        }
    }


class TestParentAuth:
    def test_register_parent(self, client: TestClient):
        data = _register_parent(client, "13900001112")
        assert data["role"] == "parent"
        assert data["child_user_id"] > 0

    def test_register_parent_duplicate_phone(self, client: TestClient):
        _register_parent(client, "13900001113")
        cap = client.get("/api/auth/captcha").json()
        res = client.post(
            "/api/auth/sms/send",
            json={
                "phone": "13900001113",
                "scene": "register",
                "captcha_id": cap["captcha_id"],
                "captcha_code": "0000",
            },
        )
        assert res.status_code == 409

    def test_parent_login_password(self, client: TestClient):
        body = _register_parent(client, "13900001114")
        res = client.post(
            "/api/auth/login",
            json={"parent_phone": "13900001114", "password": "123456", "role": "parent"},
        )
        assert res.status_code == 200
        assert res.json()["child_user_id"] == body["child_user_id"]

    def test_parent_login_wrong_password(self, client: TestClient):
        _register_parent(client, "13900001115")
        res = client.post(
            "/api/auth/login",
            json={"parent_phone": "13900001115", "password": "wrong12", "role": "parent"},
        )
        assert res.status_code == 401

    def test_parent_login_rejects_nickname_as_phone(self, client: TestClient):
        _register_parent(client, "13900001117", nickname="pyx")
        res = client.post(
            "/api/auth/login",
            json={"parent_phone": "pyx", "password": "123456", "role": "parent"},
        )
        assert res.status_code in (400, 422)
        detail = res.json().get("detail", "")
        if isinstance(detail, list):
            detail = str(detail)
        assert "手机号" in detail or "parent_phone" in detail.lower()

    def test_create_and_login_child(self, client: TestClient):
        parent = _register_parent(client, "13900001116")
        auth = _parent_auth(parent)
        res = client.post(
            "/api/parent/children",
            json={"login_name": "xiaoming", "nickname": "小明", "password": "654321"},
            **auth,
        )
        assert res.status_code == 200
        child_id = res.json()["id"]

        login = client.post(
            "/api/auth/login",
            json={"login_name": "xiaoming", "password": "654321"},
        )
        assert login.status_code == 200
        assert login.json()["child_user_id"] == child_id
        assert login.json()["role"] == "student"

    def test_list_children(self, client: TestClient):
        parent = _register_parent(client, "13900001117")
        auth = _parent_auth(parent)
        client.post(
            "/api/parent/children",
            json={"login_name": "child1", "nickname": "孩子一", "password": "111111"},
            **auth,
        )
        res = client.get("/api/parent/children", **auth)
        assert res.status_code == 200
        assert len(res.json()["children"]) == 1
        assert res.json()["children"][0]["nickname"] == "孩子一"

    def test_update_child(self, client: TestClient):
        parent = _register_parent(client, "13900001118")
        auth = _parent_auth(parent)
        created = client.post(
            "/api/parent/children",
            json={"login_name": "child2", "nickname": "旧名", "password": "111111"},
            **auth,
        ).json()
        cid = created["id"]
        res = client.put(
            f"/api/parent/children/{cid}",
            json={"nickname": "新名", "password": "222222"},
            **auth,
        )
        assert res.status_code == 200
        assert res.json()["nickname"] == "新名"
        bad = client.post(
            "/api/auth/login",
            json={"login_name": "child2", "password": "111111"},
        )
        assert bad.status_code == 401
        ok = client.post(
            "/api/auth/login",
            json={"login_name": "child2", "password": "222222"},
        )
        assert ok.status_code == 200

    def test_parent_quota(self, client: TestClient):
        parent = _register_parent(client, "13900001119")
        auth = _parent_auth(parent)
        res = client.get("/api/parent/quota", **auth)
        assert res.status_code == 200
        data = res.json()
        assert data["limit"] == 5
        assert data["can_add"] is True

    def test_student_password_login(self, client: TestClient):
        parent = _register_parent(client, "13900001120", password="123456")
        auth = _parent_auth(parent)
        created = client.post(
            "/api/parent/children",
            json={"login_name": "legacy_kid", "nickname": "旧流程童", "password": "111111"},
            **auth,
        ).json()
        res = client.post(
            "/api/auth/login",
            json={"login_name": "legacy_kid", "password": "111111"},
        )
        assert res.status_code == 200
        assert res.json()["child_user_id"] == created["id"]

    def test_child_profile_includes_parent_name(self, client: TestClient):
        parent = _register_parent(client, "13900002222", password="123456")
        auth = _parent_auth(parent)
        created = client.post(
            "/api/parent/children",
            json={"login_name": "kid01", "nickname": "孩子甲", "password": "111111"},
            **auth,
        ).json()
        cid = created["id"]
        res = client.get(f"/api/user/profile?user_id={cid}")
        assert res.status_code == 200
        data = res.json()
        assert data["parent_name"] == "张家长"
        assert data["profile_json"].get("parentName") == "张家长"

    def test_parent_set_grade_visible_on_child_profile(self, client: TestClient):
        parent = _register_parent(client, "13900003333", password="123456")
        auth = _parent_auth(parent)
        created = client.post(
            "/api/parent/children",
            json={
                "login_name": "kid_grade",
                "nickname": "刘思思",
                "password": "111111",
                "grade": "五年级",
            },
            **auth,
        ).json()
        cid = created["id"]
        assert created["grade"] == "五年级"

        res = client.get(f"/api/user/profile?user_id={cid}")
        assert res.status_code == 200
        pj = res.json()["profile_json"]
        assert pj.get("grade") == "五年级"
        assert pj.get("learner", {}).get("grade") == "五年级"

    def test_update_child_age_up_to_120(self, client: TestClient):
        parent = _register_parent(client, "13900003334")
        auth = _parent_auth(parent)
        created = client.post(
            "/api/parent/children",
            json={"login_name": "kid_age", "nickname": "年龄测试", "password": "111111"},
            **auth,
        ).json()
        res = client.put(
            f"/api/parent/children/{created['id']}",
            json={"age": 30},
            **auth,
        )
        assert res.status_code == 200, res.text

    def test_parent_profile_password_returns_new_session(self, client: TestClient):
        """改密后 API 返回新 session_token，供前端更新（生产环境会吊销旧 token）。"""
        parent = _register_parent(client, "13900003335", password="123456")
        auth = _parent_auth(parent)
        res = client.put(
            "/api/parent/profile",
            json={
                "real_name": "张三",
                "nickname": "张家长",
                "password": "654321",
                "old_password": "123456",
            },
            **auth,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("session_token")
        assert data["session_token"] != parent["session_token"]

    def test_parent_profile_password_requires_old_password(self, client: TestClient):
        parent = _register_parent(client, "13900003336", password="123456")
        auth = _parent_auth(parent)
        res = client.put(
            "/api/parent/profile",
            json={"password": "654321"},
            **auth,
        )
        assert res.status_code == 400
        assert "原密码" in res.json()["detail"]
