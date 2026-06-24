"""学科答疑 pages/qa/index.vue"""

from fastapi.testclient import TestClient


class TestModuleQa:
    def test_qa_chat_math(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "分数加法怎么算？", "subject": "数学"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"]
        assert data["reply"] == "【测试】豆包回复"
        assert data["talent_primary"] == "学者"

    def test_qa_session_persisted(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        first = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "什么是比喻？"},
        ).json()
        second = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "再举个例子", "session_id": first["session_id"]},
        )
        assert second.status_code == 200

        msgs = client.get(f"/api/qa/sessions/{first['session_id']}?user_id={uid}")
        assert len(msgs.json()["messages"]) >= 4

    def test_qa_list_sessions(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.post(f"/api/qa/chat?user_id={uid}", json={"message": "你好"})
        res = client.get(f"/api/qa/sessions?user_id={uid}")
        assert len(res.json()["items"]) >= 1
