"""同家长下切换孩子账户 — /api/auth/siblings + /api/auth/switch-child"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_parent_auth import CHILD_PWD, STRONG_PWD, _parent_auth, _register_parent


def _student_auth(login_res: dict) -> dict:
    return {
        "params": {
            "user_id": login_res["child_user_id"],
            "session_token": login_res.get("session_token", ""),
        }
    }


class TestAuthSiblings:
    def test_siblings_and_switch_child(self, client: TestClient):
        parent = _register_parent(client, "13900007701", password=STRONG_PWD)
        pauth = _parent_auth(parent)

        kid1 = client.post(
            "/api/parent/children",
            json={"login_name": "sw_kid1", "nickname": "切换童一", "password": CHILD_PWD},
            **pauth,
        ).json()
        kid2 = client.post(
            "/api/parent/children",
            json={"login_name": "sw_kid2", "nickname": "切换童二", "password": CHILD_PWD},
            **pauth,
        ).json()

        login1 = client.post(
            "/api/auth/login",
            json={"login_name": "sw_kid1", "password": CHILD_PWD},
        )
        assert login1.status_code == 200, login1.text
        uid1 = login1.json()["child_user_id"]
        auth1 = _student_auth(login1.json())

        siblings = client.get("/api/auth/siblings", **auth1)
        assert siblings.status_code == 200, siblings.text
        body = siblings.json()
        ids = {s["id"] for s in body["siblings"]}
        assert kid2["id"] in ids
        assert kid1["id"] not in ids
        assert body["current"]["id"] == uid1

        switched = client.post(
            "/api/auth/switch-child",
            params={
                "user_id": uid1,
                "session_token": login1.json().get("session_token", ""),
                "target_child_id": kid2["id"],
            },
        )
        assert switched.status_code == 200, switched.text
        data = switched.json()
        assert data["child_user_id"] == kid2["id"]
        assert data["nickname"] == "切换童二"
        assert data["role"] == "student"

    def test_switch_child_rejects_other_parent(self, client: TestClient):
        parent_a = _register_parent(client, "13900007702", password=STRONG_PWD, nickname="家长A")
        parent_b = _register_parent(client, "13900007703", password=STRONG_PWD, nickname="家长B")
        auth_a = _parent_auth(parent_a)
        auth_b = _parent_auth(parent_b)

        kid_a = client.post(
            "/api/parent/children",
            json={"login_name": "sw_kid_a", "nickname": "A童", "password": CHILD_PWD},
            **auth_a,
        ).json()
        kid_b = client.post(
            "/api/parent/children",
            json={"login_name": "sw_kid_b", "nickname": "B童", "password": CHILD_PWD},
            **auth_b,
        ).json()

        login_a = client.post(
            "/api/auth/login",
            json={"login_name": "sw_kid_a", "password": CHILD_PWD},
        )
        assert login_a.status_code == 200
        uid_a = login_a.json()["child_user_id"]

        denied = client.post(
            "/api/auth/switch-child",
            params={
                "user_id": uid_a,
                "session_token": login_a.json().get("session_token", ""),
                "target_child_id": kid_b["id"],
            },
        )
        assert denied.status_code == 403

        # sanity: cannot switch to self via wrong parent kid
        assert kid_a["id"] != kid_b["id"]

    def test_siblings_hides_removed_and_blocks_switch(self, client: TestClient, db_session: Session):
        from app.db.models import ChildUser

        parent = _register_parent(client, "13900007704", password=STRONG_PWD)
        pauth = _parent_auth(parent)
        kid1 = client.post(
            "/api/parent/children",
            json={"login_name": "sw_keep", "nickname": "测试1", "password": CHILD_PWD},
            **pauth,
        ).json()
        kid2 = client.post(
            "/api/parent/children",
            json={"login_name": "sw_gone", "nickname": "测试", "password": CHILD_PWD},
            **pauth,
        ).json()

        removed = db_session.get(ChildUser, kid2["id"])
        removed.account_status = "removed"
        db_session.commit()

        login1 = client.post(
            "/api/auth/login",
            json={"login_name": "sw_keep", "password": CHILD_PWD},
        )
        assert login1.status_code == 200, login1.text
        uid1 = login1.json()["child_user_id"]
        auth1 = _student_auth(login1.json())

        siblings = client.get("/api/auth/siblings", **auth1)
        assert siblings.status_code == 200, siblings.text
        ids = {s["id"] for s in siblings.json()["siblings"]}
        assert kid1["id"] not in ids
        assert kid2["id"] not in ids

        denied = client.post(
            "/api/auth/switch-child",
            params={
                "user_id": uid1,
                "session_token": login1.json().get("session_token", ""),
                "target_child_id": kid2["id"],
            },
        )
        assert denied.status_code == 404
