"""天赋测试 pages/talent/index.vue + pages/report/index.vue"""

from fastapi.testclient import TestClient


class TestModuleTalent:
    def test_submit_report(self, client: TestClient, mock_jnao, registered_user):
        uid = registered_user["child_user_id"]
        res = client.post(
            "/api/talent/report",
            json={
                "answer": "1" * 35,
                "uid": 123456,
                "type": 1,
                "child_user_id": uid,
            },
        )
        assert res.status_code == 200
        assert res.json()["code"] == 1
        assert res.json()["data"]["talent"] == "学者"

        latest = client.get(f"/api/talent/assessment/latest?user_id={uid}")
        assert latest.status_code == 200
        assert latest.json()["talent_code"] == 1

    def test_training_blocked_without_assessment(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/training/today?user_id={uid}")
        assert res.status_code == 403

    def test_child_type_uses_type_1(self, client: TestClient, mock_jnao):
        res = client.post(
            "/api/talent/report",
            json={"answer": "0" * 35, "uid": 1, "type": 1},
        )
        assert res.status_code == 200
        mock_jnao["submit"].assert_called_once()
        assert mock_jnao["submit"].call_args[0][2] == 1
