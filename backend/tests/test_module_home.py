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
        chat = client.post(f"/api/guide/chat?user_id={uid}", json={"message": "你好"})
        assert chat.status_code == 200
        chat_body = chat.json()
        res = client.get(f"/api/guide/session?user_id={uid}")
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"]
        assert len(data["messages"]) >= 2
        assistants = [m for m in data["messages"] if m["role"] == "assistant"]
        assert assistants
        last = assistants[-1]
        assert "actions" in last
        assert "tools_used" in last
        assert isinstance(last["actions"], list)
        assert isinstance(last["tools_used"], list)
        # 与当轮 chat 响应一致（mock 下通常有 navigate actions）
        if chat_body.get("actions"):
            assert last["actions"] == chat_body["actions"]

    def test_guide_session_empty_without_chat(self, client: TestClient, registered_user):
        """空会话不再注入静态 GREETING；开场由 /bootstrap 负责。"""
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/guide/session?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["messages"] == []
        assert res.json()["session_id"] is None

    def test_guide_debug_shows_doubao(self, client: TestClient):
        res = client.get("/api/guide/debug")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "doubao"
        assert data["key_ok"] is True

    def test_chat_legacy_removed(self, client: TestClient, registered_user):
        """旧 /api/chat 已废弃，首页统一走 /api/guide/*"""
        uid = registered_user["child_user_id"]
        res = client.post(f"/api/chat?user_id={uid}", json={"message": "你好"})
        assert res.status_code == 404

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

    def test_guide_sessions_list_and_delete(self, client: TestClient, registered_user, mock_doubao):
        uid = registered_user["child_user_id"]
        chat = client.post(
            f"/api/guide/chat?user_id={uid}",
            json={"message": "历史会话测试"},
        )
        sid = chat.json()["session_id"]
        listed = client.get(f"/api/guide/sessions?user_id={uid}")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert any(it["id"] == sid for it in items)

        detail = client.get(f"/api/guide/sessions/{sid}?user_id={uid}")
        assert detail.status_code == 200
        assert detail.json()["session_id"] == sid
        assert len(detail.json()["messages"]) >= 2
        assistants = [m for m in detail.json()["messages"] if m["role"] == "assistant"]
        assert assistants and "actions" in assistants[-1] and "tools_used" in assistants[-1]

        deleted = client.delete(f"/api/guide/sessions/{sid}?user_id={uid}")
        assert deleted.status_code == 200
        assert deleted.json()["ok"] is True
        listed2 = client.get(f"/api/guide/sessions?user_id={uid}")
        assert all(it["id"] != sid for it in listed2.json()["items"])
