"""用户端 JWT + 多端同时登录冒烟"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ChildUser, UserSession
from app.services.session_service import issue_session, validate_session


def _bearer(uid: int, token: str) -> dict:
    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Child-User-Id": str(uid),
        }
    }


def _login_student(client: TestClient, login_name: str, password: str = "XiaoMing1") -> dict:
    res = client.post(
        "/api/auth/login",
        json={"login_name": login_name, "password": password},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("access_token")
    assert data["access_token"] == data.get("session_token")
    assert data["access_token"].count(".") == 2  # JWT
    return data


def _create_child(client: TestClient, db_session, pid: int, login_name: str, nickname: str) -> int:
    parent = db_session.get(ChildUser, pid)
    assert parent is not None
    ptok = issue_session(db_session, parent)
    child = client.post(
        f"/api/parent/children?user_id={pid}",
        json={"login_name": login_name, "nickname": nickname, "password": "XiaoMing1"},
        **_bearer(pid, ptok),
    )
    assert child.status_code == 200, child.text
    return child.json()["id"]


class TestJwtMultiDevice:
    def test_two_devices_both_valid_and_single_logout(
        self, client_strict_auth: TestClient, db_session
    ):
        from tests.test_admin_api import _seed_parent

        pid = _seed_parent(db_session, "13900008801", "多端家长")
        cid = _create_child(client_strict_auth, db_session, pid, "kid_jwt_md", "JWT童")

        a = _login_student(client_strict_auth, "kid_jwt_md")
        b = _login_student(client_strict_auth, "kid_jwt_md")
        tok_a = a["access_token"]
        tok_b = b["access_token"]
        assert tok_a != tok_b

        r1 = client_strict_auth.get("/api/user/profile", **_bearer(cid, tok_a))
        r2 = client_strict_auth.get("/api/user/profile", **_bearer(cid, tok_b))
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text

        out = client_strict_auth.post("/api/auth/logout", **_bearer(cid, tok_a))
        assert out.status_code == 200, out.text

        assert client_strict_auth.get("/api/user/profile", **_bearer(cid, tok_a)).status_code == 401
        assert client_strict_auth.get("/api/user/profile", **_bearer(cid, tok_b)).status_code == 200
        assert validate_session(db_session, cid, tok_b)
        assert not validate_session(db_session, cid, tok_a)

    def test_sixth_login_trims_oldest(self, client_strict_auth: TestClient, db_session):
        from tests.test_admin_api import _seed_parent

        pid = _seed_parent(db_session, "13900008802", "超限家长")
        cid = _create_child(client_strict_auth, db_session, pid, "kid_jwt_trim", "超限童")

        tokens = [_login_student(client_strict_auth, "kid_jwt_trim")["access_token"] for _ in range(6)]
        sessions = db_session.scalars(select(UserSession).where(UserSession.user_id == cid)).all()
        assert len(sessions) == 5

        assert not validate_session(db_session, cid, tokens[0])
        for tok in tokens[1:]:
            assert validate_session(db_session, cid, tok)

        assert client_strict_auth.get("/api/user/profile", **_bearer(cid, tokens[0])).status_code == 401
        assert client_strict_auth.get("/api/user/profile", **_bearer(cid, tokens[-1])).status_code == 200

    def test_admin_login_stays_opaque_cookie_not_jwt(self, client_strict_auth: TestClient):
        res = client_strict_auth.post(
            "/api/admin/login",
            json={"login_name": "pyx", "password": "123456"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        token = data.get("session_token") or ""
        # Admin 仍 opaque（无点分隔）；不发用户端 JWT
        assert token.count(".") != 2
        assert not data.get("access_token")

        uid = data["child_user_id"]
        # Admin 忽略 Authorization Bearer；清 Cookie 后仅带 Bearer 应 401
        client_strict_auth.cookies.clear()
        ignore_bearer = client_strict_auth.get(
            "/api/admin/settings",
            headers={"Authorization": f"Bearer {token}", "X-Child-User-Id": str(uid)},
        )
        assert ignore_bearer.status_code == 401

        ok = client_strict_auth.get(
            "/api/admin/settings",
            headers={"X-Session-Token": token, "X-Child-User-Id": str(uid)},
        )
        assert ok.status_code == 200, ok.text

    def test_change_password_revokes_all(self, client_strict_auth: TestClient, db_session):
        from tests.test_parent_auth import STRONG_PWD, _register_parent

        parent = _register_parent(client_strict_auth, "13900008804", password=STRONG_PWD)
        pid = parent["child_user_id"]
        tok1 = parent["access_token"] or parent["session_token"]

        login2 = client_strict_auth.post(
            "/api/auth/login",
            json={"parent_phone": parent["parent_phone"], "password": STRONG_PWD, "role": "parent"},
        )
        assert login2.status_code == 200, login2.text
        tok2 = login2.json()["access_token"]

        assert client_strict_auth.get("/api/parent/profile", **_bearer(pid, tok1)).status_code == 200
        assert client_strict_auth.get("/api/parent/profile", **_bearer(pid, tok2)).status_code == 200

        changed = client_strict_auth.post(
            "/api/auth/change-password",
            headers={
                "Authorization": f"Bearer {tok1}",
                "X-Child-User-Id": str(pid),
                "Content-Type": "application/json",
            },
            json={"old_password": STRONG_PWD, "new_password": "NewStrong9"},
        )
        assert changed.status_code == 200, changed.text
        new_tok = changed.json().get("access_token") or changed.json().get("session_token")
        assert new_tok

        assert client_strict_auth.get("/api/parent/profile", **_bearer(pid, tok1)).status_code == 401
        assert client_strict_auth.get("/api/parent/profile", **_bearer(pid, tok2)).status_code == 401
        assert client_strict_auth.get("/api/parent/profile", **_bearer(pid, new_tok)).status_code == 200
