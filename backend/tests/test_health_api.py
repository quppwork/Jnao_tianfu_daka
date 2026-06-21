"""Health check API tests"""

import pytest
from fastapi.testclient import TestClient


class TestHealth:
    """GET /api/health"""

    def test_health_returns_status(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """健康检查返回各服务状态."""
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "integrations" in data
        assert "tianfu_rag" in data["integrations"]
