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
    return {
        "headers": {
            "X-Child-User-Id": str(uid),
            "X-Session-Token": token,
        },
    }


def _seed_parent(db_session, phone: str, nickname: str) -> int:
    from app.core.password import hash_password
    from app.services.auth_service import ROLE_PARENT, register_child
    from app.services.datetime_fmt import format_cst
    from datetime import datetime
    from app.services.training_day import TZ

    now_iso = format_cst(datetime.now(TZ).replace(tzinfo=None))
    user = register_child(
        db_session,
        parent_phone=phone,
        nickname=nickname,
        password=hash_password("123456"),
        role=ROLE_PARENT,
        child_quota=5,
    )
    user.profile_json = {
        "parent": {
            "real_name": nickname,
            "phone_verified_at": now_iso,
            "login_channel": "standard",
        }
    }
    db_session.commit()
    db_session.refresh(user)
    return user.id


class TestAdminApi:
    def test_ensure_admin_retires_legacy_admins_and_sessions(self, db_session, monkeypatch):
        from app.services import auth_service
        from app.services.session_service import issue_session, validate_session

        monkeypatch.setenv("ADMIN_LOGIN_NAME", "new_admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "1234567890123456")
        legacy = auth_service.register_child(
            db_session,
            parent_phone="admin_legacy",
            nickname="旧管理员",
            login_name="pyx_legacy",
            password="123456",
            role=auth_service.ROLE_ADMIN,
        )
        legacy_token = issue_session(db_session, legacy)
        assert validate_session(db_session, legacy.id, legacy_token)

        kept = auth_service.ensure_admin_account(db_session)
        assert kept.login_name == "new_admin"
        assert auth_service.find_admin_by_login_name(db_session, "pyx_legacy") is None
        legacy_row = db_session.get(type(legacy), legacy.id)
        assert legacy_row.account_status == auth_service.ACCOUNT_DELETED
        assert not validate_session(db_session, legacy.id, legacy_token)
        assert auth_service.login_admin_by_password(db_session, "pyx_legacy", "123456") is None

    def test_admin_login(self, client: TestClient):
        data = _admin_login(client)
        assert data["role"] == "admin"

    def test_parent_delete_forbidden(self, client: TestClient, db_session):
        pid = _seed_parent(db_session, "13900009901", "测家长")
        child = client.post(
            f"/api/parent/children?user_id={pid}",
            json={"login_name": "kid_del", "nickname": "小孩", "password": "111111"},
        ).json()
        cid = child["id"]
        res = client.delete(f"/api/parent/children/{cid}?user_id={pid}")
        assert res.status_code == 403

    def test_unbound_child_cannot_login(self, client: TestClient, db_session):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        pid = _seed_parent(db_session, "13900009902", "家长乙")
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
        pid = _seed_parent(db_session, "13900009903", "家长丙")
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

    def test_admin_update_quota(self, client: TestClient, db_session):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        pid = _seed_parent(db_session, "13900009904", "家长丁")
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

    def test_parent_detail_and_child_detail(self, client: TestClient, db_session):
        admin = _admin_login(client)
        auth = _auth_admin(admin)
        pid = _seed_parent(db_session, "13900009905", "家长戊")
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

        pid = _seed_parent(db_session, "13900009906", "家长己")
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
