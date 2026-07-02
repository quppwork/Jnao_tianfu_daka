import pytest
"""家长/孩子账号体系"""

from fastapi.testclient import TestClient


def _register_parent(client: TestClient, phone: str = "13900001111", password: str = "123456") -> dict:
    res = client.post(
        "/api/auth/register",
        json={
            "parent_phone": phone,
            "nickname": "张家长",
            "password": password,
            "role": "parent",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


class TestParentAuth:
    def test_register_parent(self, client: TestClient):
        data = _register_parent(client, "13900001112")
        assert data["role"] == "parent"
        assert data["child_user_id"] > 0

    def test_register_parent_duplicate_phone(self, client: TestClient):
        _register_parent(client, "13900001113")
        res = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900001113",
                "nickname": "李家长",
                "password": "123456",
                "role": "parent",
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

    def test_create_and_login_child(self, client: TestClient):
        parent = _register_parent(client, "13900001116")
        pid = parent["child_user_id"]
        res = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "xiaoming", "nickname": "小明", "password": "654321"},
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
        pid = parent["child_user_id"]
        client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "child1", "nickname": "孩子一", "password": "111111"},
        )
        res = client.get(f"/api/parent/children?user_id={pid}")
        assert res.status_code == 200
        assert len(res.json()["children"]) == 1
        assert res.json()["children"][0]["nickname"] == "孩子一"

    def test_update_child(self, client: TestClient):
        parent = _register_parent(client, "13900001118")
        pid = parent["child_user_id"]
        created = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "child2", "nickname": "旧名", "password": "111111"},
        ).json()
        cid = created["id"]
        res = client.put(
            f"/api/parent/children/{cid}?user_id={pid}",
            json={"nickname": "新名", "password": "222222"},
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
        pid = parent["child_user_id"]
        res = client.get(f"/api/parent/quota?user_id={pid}")
        assert res.status_code == 200
        data = res.json()
        assert data["limit"] == 5
        assert data["can_add"] is True

    def test_legacy_student_register_login(self, client: TestClient):
        """兼容旧手机+昵称注册"""
        body = {"parent_phone": "13988887777", "nickname": "_legacy"}
        r1 = client.post("/api/auth/register", json=body)
        assert r1.status_code == 200
        r2 = client.post("/api/auth/login", json=body)
        assert r2.status_code == 200

    def test_child_profile_includes_parent_name(self, client: TestClient):
        parent = _register_parent(client, "13900002222", password="123456")
        pid = parent["child_user_id"]
        created = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid01", "nickname": "孩子甲", "password": "111111"},
        ).json()
        cid = created["id"]
        res = client.get(f"/api/user/profile?user_id={cid}")
        assert res.status_code == 200
        data = res.json()
        assert data["parent_name"] == "张家长"
        assert data["profile_json"].get("parentName") == "张家长"
