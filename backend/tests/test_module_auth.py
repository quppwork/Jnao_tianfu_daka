import pytest
"""用户注册登录 — 前端进入 App 前置"""

from fastapi.testclient import TestClient


class TestModuleAuth:
    def test_register_new_user(self, client: TestClient):
        res = client.post(
            "/api/auth/register",
            json={"parent_phone": "13911112222", "nickname": "小明"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["child_user_id"] > 0
        assert data["nickname"] == "小明"

    def test_register_idempotent(self, client: TestClient):
        body = {"parent_phone": "13933334444", "nickname": "小红"}
        r1 = client.post("/api/auth/register", json=body)
        assert r1.status_code == 200
        r2 = client.post("/api/auth/register", json=body)
        assert r2.status_code == 409

    def test_login_student_password(self, client: TestClient):
        from tests.test_parent_auth import STRONG_PWD, _parent_auth, _register_parent

        parent = _register_parent(client, "13955556666", password=STRONG_PWD)
        auth = _parent_auth(parent)
        client.post(
            "/api/parent/children",
            json={"login_name": "kid_xiaogang", "nickname": "小刚", "password": "XiaoMing1"},
            **auth,
        )
        res = client.post(
            "/api/auth/login",
            json={"login_name": "kid_xiaogang", "password": "XiaoMing1"},
        )
        assert res.status_code == 200

    def test_login_invalid_credentials(self, client: TestClient):
        res = client.post(
            "/api/auth/login",
            json={"parent_phone": "13999990000", "nickname": "不存在"},
        )
        assert res.status_code == 400

    def test_profile_after_register(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/user/profile?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["parent_phone"] == registered_user["parent_phone"]
