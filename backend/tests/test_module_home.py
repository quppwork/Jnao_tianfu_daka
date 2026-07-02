import pytest
"""首页 index.vue — 引导对话 /api/guide/*"""

from fastapi.testclient import TestClient


class TestModuleHome:
    """前端：pages/index.vue"""

    def test_guide_chat(self, client: TestClient, registered_user, mock_doubao):
        uid = registered_user["child_user_id"]
        res = client.post(
            f"/api/guide/chat?user_id={uid}",
            json={"message": "天赋测试怎么做？"},
        )
        assert res.status_code == 200
        assert res.json()["reply"] == "【测试】豆包回复"
        assert res.json()["session_id"]

    def test_guide_empty_message(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.post(f"/api/guide/chat?user_id={uid}", json={"message": ""})
        assert res.status_code == 422

    def test_guide_session_load(self, client: TestClient, registered_user, mock_doubao):
        uid = registered_user["child_user_id"]
        client.post(f"/api/guide/chat?user_id={uid}", json={"message": "你好"})
        res = client.get(f"/api/guide/session?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["session_id"]
        assert len(res.json()["messages"]) >= 2

    def test_guide_session_greeting(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/guide/session?user_id={uid}")
        assert res.status_code == 200
        msgs = res.json()["messages"]
        assert msgs[0]["content"].startswith("你好！我是张宇老师")

    def test_guide_debug_shows_doubao(self, client: TestClient):
        res = client.get("/api/guide/debug")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "doubao"
        assert data["key_ok"] is True

    def test_generic_chat_also_doubao(self, client: TestClient, mock_doubao):
        """首页也可走 /api/chat"""
        res = client.post("/api/chat", json={"message": "你好"})
        assert res.json()["data"]["answer_mode"] == "doubao"

    def test_guide_chat_stream(self, client: TestClient, registered_user, mock_doubao):
        uid = registered_user["child_user_id"]
        with client.stream(
            "POST",
            f"/api/guide/chat/stream?user_id={uid}",
            json={"message": "怎么开始训练？"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = resp.read().decode()
            assert '"type": "token"' in body
            assert '"type": "done"' in body
            assert "session_id" in body
