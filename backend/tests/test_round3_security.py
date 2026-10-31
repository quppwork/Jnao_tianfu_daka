"""第三轮安全加固回归测试"""

import pytest
from fastapi.testclient import TestClient


class TestLegacyRegisterGate:
    def test_register_forbidden_when_legacy_disabled(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.api.auth.is_legacy_register_enabled", lambda: False)
        res = client.post(
            "/api/auth/register",
            json={"parent_phone": "13977778888", "nickname": "禁注册"},
        )
        assert res.status_code == 403


class TestTalentReportAuth:
    def test_report_requires_user_id(self, client: TestClient):
        res = client.post(
            "/api/talent/report",
            json={"answer": "1" * 35, "uid": 1, "type": 1},
        )
        assert res.status_code == 401


class TestGuideChatAuth:
    def test_guide_chat_requires_auth(self, client: TestClient):
        res = client.post("/api/guide/chat", json={"message": "你好"})
        assert res.status_code == 401


class TestStudentRole:
    def test_parent_rejected_on_training_entry(self, db_session, mock_jnao, mock_doubao):
        from app.core.deps import get_db
        from app.services import auth_service
        from app.services.session_service import issue_session
        from main import app

        parent = auth_service.register_child(
            db_session,
            parent_phone="13966667777",
            nickname="家长测",
            password="123456",
            role=auth_service.ROLE_PARENT,
            child_quota=3,
        )
        token = issue_session(db_session, parent)

        def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        try:
            with TestClient(app) as c:
                res = c.get(
                    f"/api/training/entry?user_id={parent.id}",
                    headers={"X-Child-User-Id": str(parent.id), "X-Session-Token": token},
                )
                assert res.status_code == 403
        finally:
            app.dependency_overrides.clear()
