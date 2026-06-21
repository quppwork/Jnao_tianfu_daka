"""Backend API tests — chat endpoint"""

import pytest
from fastapi.testclient import TestClient


class TestChatEndpoint:
    """POST /api/chat"""

    def test_normal_chat(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """正常对话请求."""
        res = client.post("/api/chat", json={
            "message": "我的天赋是什么？",
            "user_id": "test_user",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 1
        assert data["data"]["answer"] == "这是一条测试回复"
        assert len(data["data"]["sources"]) == 1
        mock_ai_proxy.chat.assert_called_once()

    def test_chat_default_user_id(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """不传 user_id 时使用默认值."""
        res = client.post("/api/chat", json={"message": "测试"})
        assert res.status_code == 200
        call_kwargs = mock_ai_proxy.chat.call_args.kwargs
        assert call_kwargs["user_id"] == "mobile_user"

    def test_chat_empty_message_422(self, client: TestClient):
        """空消息应返回 422."""
        res = client.post("/api/chat", json={"message": ""})
        assert res.status_code == 422

    def test_chat_proxy_error_returns_code_0(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """AI 服务不可用时返回 code:0 而非 500."""
        mock_ai_proxy.chat.side_effect = Exception("连接失败")
        res = client.post("/api/chat", json={"message": "测试"})
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 0
        assert "暂不可用" in data["data"]["answer"]


class TestChatStreamEndpoint:
    """GET /api/chat/stream"""

    async def _collect_sse(self, client: TestClient, message: str) -> list[str]:
        """Helper: collect SSE events from stream endpoint."""
        events: list[str] = []
        with client.stream("GET", f"/api/chat/stream?message={message}&user_id=test") as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    events.append(line[6:])
        return events

    def test_stream_returns_events(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """SSE 流式返回 token 事件."""
        async def fake_stream(**kwargs):
            yield {"type": "token", "content": "你"}
            yield {"type": "token", "content": "好"}
            yield {"type": "done"}

        mock_ai_proxy.proxy_talent_stream = fake_stream

        with client.stream("GET", "/api/chat/stream?message=你好&user_id=test") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = resp.read().decode()
            assert "data: 你" in body
            assert "data: 好" in body
            assert "data: [DONE]" in body

    def test_stream_error_handling(self, client: TestClient, mock_jnao, mock_ai_proxy):
        """流式错误时返回 ERROR 事件."""
        async def fake_stream(**kwargs):
            yield {"type": "error", "message": "上游超时"}
            yield {"type": "done"}

        mock_ai_proxy.proxy_talent_stream = fake_stream

        with client.stream("GET", "/api/chat/stream?message=test") as resp:
            body = resp.read().decode()
            assert "[ERROR]" in body
