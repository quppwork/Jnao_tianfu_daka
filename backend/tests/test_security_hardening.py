"""P0 安全加固 — bind 校验、一孩一家长"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.models import ParentChildBind
from app.services import auth_service
from app.services.session_service import issue_session


def _student_auth(client: TestClient, phone: str = "13900006601") -> dict:
    reg = client.post(
        "/api/auth/register",
        json={"parent_phone": phone, "nickname": "孤儿童", "login_name": f"kid_{phone[-4:]}", "password": "111111"},
    )
    assert reg.status_code == 200, reg.text
    data = reg.json()
    return {
        "params": {
            "user_id": data["child_user_id"],
            "session_token": data["session_token"],
        }
    }


class TestUnboundStudentBlocked:
    def test_student_api_rejects_unbound_child(self, client_strict_auth: TestClient, monkeypatch):
        monkeypatch.setattr("app.api.auth.is_legacy_register_enabled", lambda: True)
        auth = _student_auth(client_strict_auth)
        res = client_strict_auth.get("/api/user/profile", **auth)
        assert res.status_code == 403
        assert "绑定" in res.json()["detail"]

    def test_bound_student_can_access_profile(
        self, client_strict_auth: TestClient, db_session: Session, monkeypatch
    ):
        monkeypatch.setattr("app.api.auth.is_legacy_register_enabled", lambda: True)
        reg = client_strict_auth.post(
            "/api/auth/register",
            json={"parent_phone": "13900006602", "nickname": "绑定童", "login_name": "kid_bound", "password": "111111"},
        )
        data = reg.json()
        cid = data["child_user_id"]
        parent = auth_service.register_child(
            db_session,
            parent_phone="13900006602",
            nickname="家长绑",
            password="hash",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        auth_service.bind_parent_child(db_session, parent.id, cid)
        auth = {"params": {"user_id": cid, "session_token": data["session_token"]}}
        res = client_strict_auth.get("/api/user/profile", **auth)
        assert res.status_code == 200


class TestOneChildOneParent:
    def test_bind_second_parent_rejected(self, db_session: Session):
        from fastapi import HTTPException

        p1 = auth_service.register_child(
            db_session,
            parent_phone="13900006610",
            nickname="家长A",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        p2 = auth_service.register_child(
            db_session,
            parent_phone="13900006611",
            nickname="家长B",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        child = auth_service.register_child(
            db_session,
            parent_phone="13900006610",
            nickname="孩子X",
            login_name="kid_x_one",
            role=auth_service.ROLE_STUDENT,
        )
        auth_service.bind_parent_child(db_session, p1.id, child.id)
        with pytest.raises(HTTPException) as exc:
            auth_service.bind_parent_child(db_session, p2.id, child.id)
        assert exc.value.status_code == 409

    def test_admin_bind_other_parent_rejected(self, client: TestClient, db_session: Session):
        from tests.test_admin_api import _admin_login, _auth_admin

        admin = _admin_login(client)
        auth = _auth_admin(admin)
        p1 = auth_service.register_child(
            db_session,
            parent_phone="13900006620",
            nickname="管绑A",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        p2 = auth_service.register_child(
            db_session,
            parent_phone="13900006621",
            nickname="管绑B",
            role=auth_service.ROLE_PARENT,
            child_quota=5,
        )
        child = auth_service.register_child(
            db_session,
            parent_phone="13900006620",
            nickname="管孩",
            login_name="kid_admin_bind",
            role=auth_service.ROLE_STUDENT,
        )
        auth_service.bind_parent_child(db_session, p1.id, child.id)
        res = client.post(
            f"/api/admin/children/{child.id}/bind",
            json={"parent_id": p2.id},
            **auth,
        )
        assert res.status_code == 409
