"""管理员 API 测试"""

from fastapi.testclient import TestClient


def _admin_login(client: TestClient) -> dict:
    res = client.post(
        "/api/admin/login",
        json={"login_name": "pyx", "password": "123456"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _auth_admin(data: dict) -> dict:
    uid = data["child_user_id"]
    token = data["session_token"]
    return {"params": {"user_id": uid, "session_token": token}}


class TestAdminApi:
    def test_admin_login(self, client: TestClient):
        data = _admin_login(client)
        assert data["role"] == "admin"

    def test_parent_delete_forbidden(self, client: TestClient):
        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009901",
                "nickname": "测家长",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_del", "nickname": "小孩", "password": "111111"},
        ).json()
        cid = child["id"]
        res = client.delete(f"/api/parent/children/{cid}?user_id={pid}")
        assert res.status_code == 403

    def test_unbound_child_cannot_login(self, client: TestClient):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009902",
                "nickname": "家长乙",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_unbind", "nickname": "解绑童", "password": "111111"},
        ).json()
        cid = child["id"]
        client.delete(f"/api/admin/children/{cid}/bind", **auth)
        login = client.post(
            "/api/auth/login",
            json={"login_name": "kid_unbind", "password": "111111"},
        )
        assert login.status_code == 403

    def test_admin_delete_child_archived_and_reuse_login_name(self, client: TestClient, db_session):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009903",
                "nickname": "家长丙",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_hard", "nickname": "硬删童", "password": "111111"},
        ).json()
        cid = child["id"]
        res = client.delete(f"/api/admin/children/{cid}", **auth)
        assert res.status_code == 200

        archived = db_session.get(__import__("app.db.models", fromlist=["ChildUser"]).ChildUser, cid)
        assert archived is not None
        assert archived.account_status == "deleted"
        assert archived.profile_json.get("archived_login_name") == "kid_hard"

        login = client.post(
            "/api/auth/login",
            json={"login_name": "kid_hard", "password": "111111"},
        )
        assert login.status_code == 401

        recreated = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_hard", "nickname": "新童", "password": "222222"},
        )
        assert recreated.status_code == 200
        assert recreated.json()["login_name"] == "kid_hard"

    def test_admin_update_quota(self, client: TestClient):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009904",
                "nickname": "家长丁",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        res = client.put(
            f"/api/admin/parents/{pid}",
            json={"child_quota": 2},
            **auth,
        )
        assert res.status_code == 200
        assert res.json()["child_quota"] == 2

    def test_admin_settings_default(self, client: TestClient):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        res = client.get("/api/admin/settings", **auth)
        assert res.status_code == 200
        policy = res.json()["login_policy"]
        assert policy["admin_max_devices"] == 3
        assert policy["parent_max_devices"] == 1
        assert policy["student_max_devices"] == 1

    def test_admin_settings_update(self, client: TestClient):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        res = client.put(
            "/api/admin/settings",
            json={"login_policy": {"parent_max_devices": 2}},
            **auth,
        )
        assert res.status_code == 200
        assert res.json()["login_policy"]["parent_max_devices"] == 2

    def test_parent_detail_and_child_detail(self, client: TestClient):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009905",
                "nickname": "家长戊",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_detail", "nickname": "详情童", "password": "111111"},
        ).json()
        cid = child["id"]

        pres = client.get(f"/api/admin/parents/{pid}/detail", **auth)
        assert pres.status_code == 200
        pdata = pres.json()
        assert pdata["parent_phone"] == "13900009905"
        assert any(c["id"] == cid for c in pdata["children"])

        cres = client.get(f"/api/admin/children/{cid}/detail", **auth)
        assert cres.status_code == 200
        cdata = cres.json()
        assert cdata["login_name"] == "kid_detail"
        assert cdata["parent_id"] == pid

    def test_student_single_device_login(self, client: TestClient, db_session):
        from app.db.models import UserSession
        from sqlalchemy import select

        reg = client.post(
            "/api/auth/register",
            json={
                "parent_phone": "13900009906",
                "nickname": "家长己",
                "password": "123456",
                "role": "parent",
            },
        )
        pid = reg.json()["child_user_id"]
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_single", "nickname": "单端童", "password": "111111"},
        ).json()
        cid = child["id"]

        login1 = client.post(
            "/api/auth/login",
            json={"login_name": "kid_single", "password": "111111"},
        )
        assert login1.status_code == 200
        token1 = login1.json()["session_token"]

        login2 = client.post(
            "/api/auth/login",
            json={"login_name": "kid_single", "password": "111111"},
        )
        assert login2.status_code == 200
        token2 = login2.json()["session_token"]
        assert token1 != token2

        from app.services.session_service import validate_session

        assert not validate_session(db_session, cid, token1)
        assert validate_session(db_session, cid, token2)

        sessions = db_session.scalars(
            select(UserSession).where(UserSession.user_id == cid)
        ).all()
        assert len(sessions) == 1
