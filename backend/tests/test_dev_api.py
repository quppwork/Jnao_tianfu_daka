"""开发者训练 API 测试"""

from datetime import date

from app.services.dev_training_service import reset_today_training, simulate_next_training_day
from app.services.training_service import get_or_create_today_plan, submit_checkin


class TestDevTraining:
    def test_reset_today(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.get(f"/api/training/today?user_id={uid}")
        res = client.post(f"/api/dev/training/reset-today?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["action"] == "reset_today"
        assert res.json()["status"]["today_plan_id"] is None

    def test_next_day_advances_index(self, client, db_session, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        plan1 = get_or_create_today_plan(db_session, uid, date.today())
        submit_checkin(db_session, uid, plan_id=plan1["plan_id"])

        res = client.post(f"/api/dev/training/next-day?user_id={uid}")
        assert res.status_code == 200
        body = res.json()
        assert body["action"] == "next_day"
        assert body["today"]["content_index"] == plan1["content_index"] + 1

    def test_reset_all_clears_history(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.get(f"/api/training/today?user_id={uid}")
        client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": client.get(f"/api/training/today?user_id={uid}").json()["plan_id"]},
        )
        res = client.post(f"/api/dev/training/reset-all?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["status"]["plan_count"] == 0
        assert res.json()["status"]["record_count"] == 0

    def test_dev_status(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.get(f"/api/dev/training/status?user_id={uid}")
        assert res.status_code == 200
        assert "content_index" in res.json()
