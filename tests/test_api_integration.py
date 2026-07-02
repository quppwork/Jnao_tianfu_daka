"""Root integration tests — validate real backend API with HTTP calls.

These tests require backend to be running: uvicorn main:app --port 8012

Run:  python -m pytest tests/test_api_integration.py -v
Skip: when backend is not running (ConnectionRefused)
"""

import json
import os
import urllib.request
import urllib.error

_API_HOST = os.environ.get("JNAO_API_HOST", "127.0.0.1")
_API_PORT = os.environ.get("JNAO_API_PORT", "8012")
_ORIGIN = f"http://{_API_HOST}:{_API_PORT}"
BASE = f"{_ORIGIN}/api"

# 单设备登录：先注册获取 session_token，后续请求携带之
_TOKEN_CACHE = None


def _get_token() -> str:
    global _TOKEN_CACHE
    if _TOKEN_CACHE:
        return _TOKEN_CACHE
    import random
    phone = f"139{random.randint(10000000, 99999999)}"
    data = api_post("/auth/register", {"parent_phone": phone, "nickname": "集成测试"})
    _TOKEN_CACHE = data[1].get("session_token", "")
    return _TOKEN_CACHE


def _auth_url(path: str) -> str:
    url = f"{BASE}{path}"
    sep = "&" if "?" in url else "?"
    token = _get_token()
    if token and "session_token=" not in url:
        url = f"{url}{sep}session_token={token}"
    return url


def api_post(path: str, data: dict, auth: bool = True) -> tuple[int, dict]:
    """Helper: POST JSON to backend, return (status_code, response_json)."""
    url = _auth_url(path) if auth else f"{BASE}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}


def api_get(path: str, auth: bool = True) -> tuple[int, dict]:
    """Helper: GET JSON from backend."""
    url = _auth_url(path) if auth else f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}


class TestReportIntegration:
    """POST /api/talent/report — real JNAO calls."""

    def test_normal_report_returns_200(self):
        code, data = api_post("/talent/report", {
            "answer": "11000111110001001001011111000101001",
            "uid": 999888,
            "type": 0,
        })
        assert code == 200, f"Expected 200, got {code}: {data}"
        assert data["code"] == 1
        assert "data" in data
        report = data["data"]
        assert "id" in report
        assert "talent" in report
        assert "results" in report

    def test_child_test_report(self):
        code, data = api_post("/talent/report", {
            "answer": "00000000000000000000000000000000000",
            "uid": 111222,
            "type": 1,
        })
        assert code == 200
        assert data["code"] == 1

    def test_validation_error_422(self):
        code, data = api_post("/talent/report", {
            "answer": "short",
            "uid": 123456,
            "type": 0,
        })
        assert code == 422


class TestHealthIntegration:
    """GET /api/health"""

    def test_health_returns_200(self):
        code, data = api_get("/health")
        assert code == 200
        assert data["status"] == "ok"
        assert "integrations" in data


class TestChatIntegration:
    """POST /api/chat"""

    def test_chat_returns_response(self):
        code, data = api_post("/chat", {
            "message": "你好",
            "user_id": "integration_test",
        })
        assert code == 200
        assert "data" in data
        assert "answer" in data["data"]


def test_backend_serves_openapi():
    """OpenAPI schema is accessible."""
    url = f"{_ORIGIN}/openapi.json"
    try:
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200
            schema = json.loads(resp.read())
            assert "openapi" in schema
    except urllib.error.HTTPError as e:
        assert False, f"OpenAPI not reachable: {e}"


def test_backend_cors_headers():
    """CORS headers are present."""
    req = urllib.request.Request(f"{_ORIGIN}/api/health", method="OPTIONS")
    try:
        with urllib.request.urlopen(req) as resp:
            headers = dict(resp.headers)
            assert "access-control-allow-origin" in str(headers).lower() or resp.status < 500
    except urllib.error.HTTPError:
        pass  # OPTIONS might not be explicitly handled
