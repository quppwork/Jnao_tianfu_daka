"""训练课表 — 首日固定 / 次日随机"""

from datetime import timedelta

import pytest

from app.services.training_day import get_training_day
from app.services.training_curriculum import (
    is_first_training_day,
    route_day_one,
    route_random,
    route_training_blocks,
)
from app.services.training_schedule_service import schedule_training_by_duration
from app.services.training_service import get_or_create_today_plan, submit_checkin


class TestTrainingCurriculum:
    def test_first_day_detection(self):
        assert is_first_training_day(0) is True
        assert is_first_training_day(1) is False

    def test_day_one_fixed_ids(self, db_session, child_with_assessment):
        from app.services.training_service import get_content_series

        a = get_content_series(db_session, 1, series="chaonaoaomi")
        b = get_content_series(db_session, 1, series="xuekeaomi")
        if not a:
            pytest.skip("no chaonaoaomi content")
        route = route_day_one(a, b)
        assert route["mode"] == "day_one_fixed"
        assert route["training_a_ids"]
        assert "首日" in route["note"]

    def test_random_stable_same_day(self, db_session, child_with_assessment):
        from app.services.training_service import get_content_series

        a = get_content_series(db_session, 1, series="chaonaoaomi")
        b = get_content_series(db_session, 1, series="xuekeaomi")
        if len(a) < 2:
            pytest.skip("not enough content")
        r1 = route_random(a, b, 45, content_index=1, seed_key="u1:2026-06-23:1")
        r2 = route_random(a, b, 45, content_index=1, seed_key="u1:2026-06-23:1")
        assert r1["training_a_ids"] == r2["training_a_ids"]
        assert r1["mode"] == "random"


class TestScheduleDayProgression:
    @pytest.mark.asyncio
    async def test_day_one_schedule_fixed(self, db_session, child_with_assessment):
        uid = child_with_assessment
        plan = await schedule_training_by_duration(db_session, uid, 45)
        assert plan["schedule_mode"] == "day_one_fixed"
        assert plan["lesson_day"] == 1
        assert "首日" in (plan.get("report_text") or "")

    @pytest.mark.asyncio
    async def test_day_two_schedule_random(self, db_session, child_with_assessment):
        from app.db.models import TrainingPlan

        uid = child_with_assessment
        yesterday = get_training_day() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, uid, yesterday)
        plan = db_session.get(TrainingPlan, y["plan_id"])
        plan.status = "completed"
        for item in plan.items:
            item.checkin_status = "done"
        db_session.commit()
        get_or_create_today_plan(db_session, uid, get_training_day())

        plan = await schedule_training_by_duration(db_session, uid, 45)
        assert plan["schedule_mode"] == "random"
        assert plan["lesson_day"] == 2

    def test_incomplete_yesterday_keeps_index(self, db_session, child_with_assessment):
        uid = child_with_assessment
        yesterday = get_training_day() - timedelta(days=1)
        y = get_or_create_today_plan(db_session, uid, yesterday)
        today = get_or_create_today_plan(db_session, uid, get_training_day())
        assert today["content_index"] == y["content_index"]
        assert today["content_index"] == 0
