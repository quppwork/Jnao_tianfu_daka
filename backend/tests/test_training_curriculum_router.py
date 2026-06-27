"""首日主线 A 排课测试"""

import pytest

from app.services.training_curriculum_router import route_curriculum_day_one


class TestCurriculumDayOne:
    def test_day_one_duration_pack_90(self, db_session, child_with_assessment):
        route = route_curriculum_day_one(
            db_session, 1, planned_minutes=90, talent_primary="学者"
        )
        assert route["mode"] == "curriculum_day_one"
        assert "精力恢复" not in route["note"]
        assert "主线A" in route["note"]
        slots = {p.get("training_slot") for p in route["plan_items"]}
        assert 2 in slots
        ph_skills = [
            p["placeholder_skill"]
            for p in route["plan_items"]
            if p.get("placeholder_skill")
        ]
        slot2 = [p for p in route["plan_items"] if p.get("training_slot") == 2]
        assert slot2
        assert ph_skills or any(p.get("content_item_id") for p in slot2)

    @pytest.mark.asyncio
    async def test_schedule_30_min_one_item(self, db_session, child_with_assessment):
        from app.services.training_schedule_service import schedule_training_by_duration

        uid = child_with_assessment
        plan = await schedule_training_by_duration(db_session, uid, 30)
        items = plan.get("items") or []
        assert len(items) == 1
        assert items[0].get("block") == "A"

    @pytest.mark.asyncio
    async def test_schedule_first_day_mode(self, db_session, child_with_assessment):
        from app.services.training_schedule_service import schedule_training_by_duration

        uid = child_with_assessment
        plan = await schedule_training_by_duration(db_session, uid, 90)
        assert plan["schedule_mode"] in (
            "curriculum_day_one",
            "curriculum_loop",
            "day_one_fixed",
        )
        titles = [i.get("title") or "" for i in plan.get("items") or []]
        assert not any("精力恢复" in t for t in titles)
        blocks = {i.get("block") for i in plan.get("items") or []}
        assert "B" in blocks or "T3" in blocks
