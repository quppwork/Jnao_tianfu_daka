"""会话持久化 — 模拟刷新后 token 仍有效（真实 session 校验）"""

from fastapi.testclient import TestClient


def _auth_params(data: dict) -> dict:
    return {
        "params": {
            "user_id": data["child_user_id"],
            "session_token": data["session_token"],
        }
    }


class TestSessionRefresh:
    """刷新场景：同一 session_token 连续请求应成功，错误 token 应 401。"""

    def test_student_profile_survives_repeated_calls(self, client_strict_auth: TestClient):
        reg = client_strict_auth.post(
            "/api/auth/register",
            json={"parent_phone": "13900007700", "nickname": "刷新童"},
        )
        assert reg.status_code == 200, reg.text
        user = reg.json()
        auth = _auth_params(user)

        for _ in range(3):
            res = client_strict_auth.get("/api/user/profile", **auth)
            assert res.status_code == 200, res.text
            assert res.json()["parent_phone"] == user["parent_phone"]

    def test_parent_profile_survives_repeated_calls(self, client_strict_auth: TestClient):
        from tests.test_parent_auth import _register_parent

        parent = _register_parent(client_strict_auth, "13900007701", password="123456")
        auth = _auth_params(parent)

        for _ in range(3):
            res = client_strict_auth.get("/api/parent/profile", **auth)
            assert res.status_code == 200, res.text
            assert res.json()["parent_phone"] == parent["parent_phone"]

    def test_admin_settings_survives_repeated_calls(self, client_strict_auth: TestClient):
        res = client_strict_auth.post(
            "/api/admin/login",
            json={"login_name": "pyx", "password": "123456"},
        )
        assert res.status_code == 200, res.text
        auth = _auth_params(res.json())

        for _ in range(3):
            res = client_strict_auth.get("/api/admin/settings", **auth)
            assert res.status_code == 200, res.text
            assert "login_policy" in res.json()

    def test_wrong_token_returns_401_not_500(self, client_strict_auth: TestClient):
        reg = client_strict_auth.post(
            "/api/auth/register",
            json={"parent_phone": "13900007702", "nickname": "错token童"},
        )
        uid = reg.json()["child_user_id"]
        res = client_strict_auth.get(
            "/api/user/profile",
            params={"user_id": uid, "session_token": "invalid-token-xyz"},
        )
        assert res.status_code == 401

    def test_admin_401_does_not_affect_student_token(self, client_strict_auth: TestClient):
        reg = client_strict_auth.post(
            "/api/auth/register",
            json={"parent_phone": "13900007703", "nickname": "隔离童"},
        )
        user = reg.json()
        stu_auth = _auth_params(user)

        client_strict_auth.get(
            "/api/admin/settings",
            params={"user_id": 999, "session_token": "bad-admin"},
        )

        ok = client_strict_auth.get("/api/user/profile", **stu_auth)
        assert ok.status_code == 200
