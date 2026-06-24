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
        r2 = client.post("/api/auth/register", json=body)
        assert r1.json()["child_user_id"] == r2.json()["child_user_id"]

    def test_login_existing(self, client: TestClient):
        body = {"parent_phone": "13955556666", "nickname": "小刚"}
        client.post("/api/auth/register", json=body)
        res = client.post("/api/auth/login", json=body)
        assert res.status_code == 200

    def test_login_not_found(self, client: TestClient):
        res = client.post(
            "/api/auth/login",
            json={"parent_phone": "13999990000", "nickname": "不存在"},
        )
        assert res.status_code == 404

    def test_profile_after_register(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/user/profile?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["parent_phone"] == registered_user["parent_phone"]
