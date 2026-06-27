"""今日训练 pages/training/index.vue"""

from datetime import timedelta

from app.services.training_day import get_training_day
from app.services.training_service import get_or_create_today_plan


def _schedule_today(client, uid, minutes=45):
    res = client.post(f"/api/training/schedule?user_id={uid}", json={"planned_minutes": minutes})
    assert res.status_code == 200, res.text
    return res.json()


class TestModuleTraining:
    def test_today_plan_has_audio(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        _schedule_today(client, uid)
        res = client.get(f"/api/training/today?user_id={uid}")
        assert res.status_code == 200
        data = res.json()
        assert any(
            i.get("audio_url") or i.get("item_type") == "placeholder"
            for i in data["items"]
        )
        assert data["status"] == "pending"
        assert data["report_text"]

    def test_checkin_flow(self, client, user_ready_for_training, mock_doubao):
        uid = user_ready_for_training
        _schedule_today(client, uid)
        plan = client.get(f"/api/training/today?user_id={uid}").json()
        res = client.post(
            f"/api/training/checkin?user_id={uid}",
            json={"plan_id": plan["plan_id"], "attitude_pct": 80, "cards": [{"name": "影像追忆", "time": "1"}]},
        )
        assert res.status_code == 200
        assert res.json()["plan_status"] in ("pending", "completed")

        progress = client.get(f"/api/training/progress?user_id={uid}").json()
        assert progress["total_checkins"] >= 1

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
        _schedule_today(client, uid)
        client.get(f"/api/training/today?user_id={uid}")
        res = client.get(f"/api/training/report/today?user_id={uid}")
        assert res.status_code == 200
        assert res.json()["report_text"]

    def test_continue_incomplete_yesterday(self, db_session, child_with_assessment):
        yesterday = get_training_day() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        today = get_or_create_today_plan(db_session, child_with_assessment, get_training_day())
        assert today["content_index"] == y["content_index"]

    def test_advance_after_yesterday_checkin(self, db_session, child_with_assessment):
        from app.db.models import TrainingPlan

        yesterday = get_training_day() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        plan = db_session.get(TrainingPlan, y["plan_id"])
        plan.status = "completed"
        for item in plan.items:
            item.checkin_status = "done"
        db_session.commit()
        today = get_or_create_today_plan(db_session, child_with_assessment, get_training_day())
        assert today["content_index"] == y["content_index"] + 1

    def test_yesterday_context_after_checkin(self, db_session, child_with_assessment):
        from app.db.models import TrainingPlan, TrainingRecord
        from app.services.training_service import get_yesterday_training_context

        yesterday = get_training_day() - timedelta(days=1)
        plan_y = get_or_create_today_plan(db_session, child_with_assessment, yesterday)
        plan = db_session.get(TrainingPlan, plan_y["plan_id"])
        plan.status = "completed"
        item = plan.items[0]
        item.checkin_status = "done"
        db_session.add(
            TrainingRecord(
                child_user_id=child_with_assessment,
                plan_id=plan.id,
                item_id=item.id,
                ability_type="极速运算",
                attitude_pct=80,
                content="完成20题",
            )
        )
        db_session.commit()
        ctx = get_yesterday_training_context(db_session, child_with_assessment)
        assert ctx
        assert "昨日已完成" in ctx
        assert "极速运算" in ctx
