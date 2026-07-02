import pytest
"""安全开关与参数校验"""

import pytest
from fastapi.testclient import TestClient


class TestSecurityGates:
    def test_guide_debug_available_in_dev(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("JNAO_DEBUG_ROUTES", "1")
        monkeypatch.setenv("JNAO_ENV", "development")
        res = client.get("/api/guide/debug")
        assert res.status_code == 200

    def test_report_rejects_invalid_answer(self, client: TestClient):
        res = client.post(
            "/api/talent/report",
            json={"answer": "x" * 35, "uid": 1, "type": 0},
        )
        assert res.status_code == 422

    def test_history_rejects_invalid_user_id(self, client: TestClient):
        res = client.get("/api/talent/assessment/history?user_id=0")
        assert res.status_code == 422
