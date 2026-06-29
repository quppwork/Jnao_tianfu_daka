"""开发者训练 API 测试"""

from app.services.training_day import get_training_day
from app.services.training_service import _get_plan_by_date, submit_checkin


class TestDevTraining:
    def test_reset_today(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        res = client.post(f"/api/dev/training/reset-today?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["action"] == "reset_today"
        assert res.json()["status"]["today_plan_id"] is None
        regen = client.get(f"/api/training/today?user_id={uid}&skip_ai=1").json()
        assert regen["plan_id"] > 0
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        regen = client.get(f"/api/training/today?user_id={uid}&skip_ai=1").json()
        assert len(regen["items"]) >= 1

    def test_simulate_4am_preserves_yesterday_plan(self, client, db_session, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        day1 = get_training_day()

        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        plan1 = client.get(f"/api/training/today?user_id={uid}&skip_ai=1").json()
        submit_checkin(db_session, uid, plan_id=plan1["plan_id"])

        res = client.post(f"/api/dev/training/next-day?user_id={uid}")
        assert res.status_code == 200
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        client.get(f"/api/training/today?user_id={uid}&skip_ai=1").json()

        prev_plan = _get_plan_by_date(db_session, uid, day1)
        assert prev_plan is not None

        cutoff_res = client.post(f"/api/dev/training/simulate-4am-cutoff?user_id={uid}")
        assert cutoff_res.status_code == 200
        body = cutoff_res.json()
        assert body["action"] == "simulate_4am_cutoff"
        assert body["dev_time_override"]
        assert body["today_plan"]["globally_cutoff"] is True

        still_there = _get_plan_by_date(db_session, uid, day1)
        assert still_there is not None
        assert still_there.id == prev_plan.id
        assert cutoff_res.json()["status"]["record_count"] >= 1

    def test_reset_today_does_not_clear_dev_clock(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        client.post(f"/api/dev/training/simulate-4am-cutoff?user_id={uid}")
        status_before = client.get(f"/api/dev/training/status?user_id={uid}").json()
        assert status_before["dev_time_override"]

        client.post(f"/api/dev/training/reset-today?user_id={uid}")
        status_after = client.get(f"/api/dev/training/status?user_id={uid}").json()
        assert status_after["dev_time_override"] == status_before["dev_time_override"]

    def test_next_day_advances_index(self, client, db_session, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        plan1 = client.post(
            f"/api/training/schedule?user_id={uid}",
            json={"planned_minutes": 45},
        ).json()
        submit_checkin(db_session, uid, plan_id=plan1["plan_id"])

        res = client.post(f"/api/dev/training/next-day?user_id={uid}")
        assert res.status_code == 200
        body = res.json()
        assert body["action"] == "next_day"
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        plan2 = client.get(f"/api/training/today?user_id={uid}&skip_ai=1").json()
        assert plan2["plan_id"] > 0
        assert len(plan2["items"]) >= 1

        assert plan2["content_index"] == plan1["content_index"] + 1

    def test_reset_all_clears_history(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        scheduled = client.post(
            f"/api/training/schedule?user_id={uid}",
            json={"planned_minutes": 45},
        ).json()
        client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": scheduled["plan_id"]},
        )
        res = client.post(f"/api/dev/training/reset-all?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["status"]["plan_count"] == 0
        assert res.json()["status"]["record_count"] == 0

    def test_reset_talent_clears_assessment(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": 45})
        res = client.post(f"/api/dev/training/reset-talent?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["action"] == "reset_talent"
        assert res.json()["deleted_assessment"] is True
        entry = client.get(f"/api/training/entry?user_id={uid}").json()
        assert entry["needs_assessment"] is True
        assert client.get(f"/api/training/today?user_id={uid}").status_code == 403

    def test_dev_status(self, client, child_with_assessment, mock_doubao):
        uid = child_with_assessment
        res = client.get(f"/api/dev/training/status?user_id={uid}")
        assert res.status_code == 200
        assert "content_index" in res.json()
