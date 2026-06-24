"""Health check API tests"""

from fastapi.testclient import TestClient


class TestHealth:
    def test_health_returns_status(self, client: TestClient, mock_doubao):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("ok", "degraded")
        assert "integrations" in data
        assert data["integrations"]["mysql"]["connected"] is True
        assert data["integrations"]["doubao"]["connected"] is True
        assert data["integrations"]["doubao"]["status"] == "live"
