"""首页 index.vue — 引导对话 /api/guide/*"""

from fastapi.testclient import TestClient


class TestModuleHome:
    """前端：pages/index.vue"""

    def test_guide_chat(self, client: TestClient, mock_doubao):
        res = client.post("/api/guide/chat", json={"message": "天赋测试怎么做？"})
        assert res.status_code == 200
        assert res.json()["reply"] == "【测试】豆包回复"

    def test_guide_empty_message(self, client: TestClient):
        res = client.post("/api/guide/chat", json={"message": ""})
        assert res.status_code == 200
        assert "请输入" in res.json()["reply"]

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
