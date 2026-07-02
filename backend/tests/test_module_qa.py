import pytest
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

    def test_qa_delete_session_with_messages(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        chat = client.post(f"/api/qa/chat?user_id={uid}", json={"message": "测试删除会话"}).json()
        sid = chat["session_id"]
        res = client.delete(f"/api/qa/sessions/{sid}?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["ok"] is True
        gone = client.get(f"/api/qa/sessions/{sid}?user_id={uid}")
        assert gone.status_code == 404
        items = client.get(f"/api/qa/sessions?user_id={uid}").json()["items"]
        assert all(i["id"] != sid for i in items)

    def test_qa_typical_math_question(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "长方形长8厘米宽5厘米，面积怎么算？", "subject": "数学"},
        )
        assert res.status_code == 200
        assert res.json()["session_id"]
        assert res.json().get("subject_mismatch") is not True

    def test_qa_typical_chinese_question(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={"message": "《静夜思》表达了诗人怎样的情感？请结合意象分析。", "subject": "语文"},
        )
        assert res.status_code == 200
        assert res.json().get("subject_mismatch") is not True

    def test_qa_typical_english_question(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={
                "message": "过去进行时和一般过去时有什么区别？请用例句说明。",
                "subject": "英语",
            },
        )
        assert res.status_code == 200
        assert res.json().get("subject_mismatch") is not True

    def test_qa_subject_mismatch_reminds_switch(self, client: TestClient, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.post(
            f"/api/qa/chat?user_id={uid}",
            json={
                "message": "请翻译这句话：I love reading books every day.",
                "subject": "数学",
            },
        )
        data = res.json()
        assert res.status_code == 200
        assert data["subject_mismatch"] is True
        assert data["suggested_subject"] == "英语"
        assert "英语" in data["reply"]
        assert mock_doubao["chat"].call_count == 0
