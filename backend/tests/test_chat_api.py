import pytest
"""POST /api/chat — 豆包对话"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestChatEndpoint:
    def test_normal_chat(self, client: TestClient):
        res = client.post("/api/chat", json={
            "message": "我的天赋是什么？",
            "user_id": "test_user",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 1
        assert data["data"]["answer"] == "【测试】豆包回复"
        assert data["data"]["answer_mode"] == "doubao"

    def test_chat_with_history(self, client: TestClient):
        res = client.post("/api/chat", json={
            "message": "继续说说",
            "history": [{"role": "user", "content": "你好"}],
        })
        assert res.status_code == 200
        assert res.json()["code"] == 1

    def test_chat_empty_message_422(self, client: TestClient):
        res = client.post("/api/chat", json={"message": ""})
        assert res.status_code == 422

    def test_chat_doubao_error_returns_code_0(self, client: TestClient):
        with patch("app.api.chat.chat_completion", new_callable=AsyncMock, return_value=None):
            res = client.post("/api/chat", json={"message": "测试"})
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 0
        assert "暂不可用" in data["data"]["answer"]


class TestChatStreamEndpoint:
    def test_stream_returns_events(self, client: TestClient):
        with client.stream("GET", "/api/chat/stream?message=你好&user_id=test") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = resp.read().decode()
            assert "data: 你" in body
            assert "data: 好" in body
            assert "data: [DONE]" in body

    def test_stream_not_configured(self, client: TestClient):
        with patch("app.api.chat.is_configured", return_value=False):
            with client.stream("GET", "/api/chat/stream?message=test") as resp:
                body = resp.read().decode()
                assert "[ERROR]" in body
