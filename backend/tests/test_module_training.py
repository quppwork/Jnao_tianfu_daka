"""今日训练 pages/training/index.vue"""

from datetime import date, timedelta

from app.services.training_service import get_or_create_today_plan, submit_checkin


class TestModuleTraining:
    def test_today_plan_has_audio(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        res = client.get(f"/api/training/today?user_id={uid}")
        assert res.status_code == 200
        data = res.json()
        assert data["items"][0]["audio_url"]
        assert data["status"] == "pending"
        assert data["report_text"]

    def test_checkin_flow(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": plan["plan_id"], "attitude_pct": 80},
        )
        assert res.status_code == 200
        assert res.json()["plan_status"] == "completed"

        progress = client.get(f"/api/training/progress?user_id={uid}").json()
        assert progress["today_completed"] is True

    def test_training_window(self, client, user_ready_for_training):
        uid = user_ready_for_training
        client.post(
            f"/api/training/window?user_id={uid}",
            json={"start_time": "08:00", "end_time": "22:00"},
        )
        res = client.get(f"/api/training/window?user_id={uid}")
        assert res.status_code == 200

    def test_ai_report_today(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        res = client.get(f"/api/training/report/today?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["report_text"]

    def test_continue_incomplete_yesterday(self, db_session, child_with_assessment):
        yesterday = date.today() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        today = get_or_create_today_plan(db_session, child_with_assessment, date.today())
        assert today["content_index"] == y["content_index"]

    def test_advance_after_yesterday_checkin(self, db_session, child_with_assessment):
        yesterday = date.today() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        submit_checkin(db_session, child_with_assessment, plan_id=y["plan_id"])
        today = get_or_create_today_plan(db_session, child_with_assessment, date.today())
        assert today["content_index"] == y["content_index"] + 1

    def test_yesterday_context_after_checkin(self, db_session, child_with_assessment):
        from app.services.training_service import get_yesterday_training_context

        yesterday = date.today() - timedelta(days=1)
        plan_y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        submit_checkin(
            db_session,
            child_with_assessment,
            plan_id=plan_y["plan_id"],
            ability_type="极速运算",
            attitude_pct=80,
            content="完成20题",
        )
        ctx = get_yesterday_training_context(db_session, child_with_assessment)
        assert ctx
        assert "昨日已完成" in ctx
        assert "极速运算" in ctx
