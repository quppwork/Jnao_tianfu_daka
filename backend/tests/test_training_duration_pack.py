"""时长装箱：训练项数量 × 轮次 × 天赋权重辅练"""

import pytest

from app.services.training_curriculum_scheduler import build_curriculum_schedule
from app.services.training_duration_pack import pack_main_line_plan_items
from config.loader import load_training_curriculum


class TestDurationPack:
    def test_90_min_two_items_scholar(self, db_session, child_with_assessment):
        uid = child_with_assessment
        from app.db.models import ChildUser
        from app.services.child_training_state import get_training_progress

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        cur = load_training_curriculum()
        line = cur["main_lines"]["A"]
        from app.services.talent_content_pool import get_talent_content_pool

        pool = get_talent_content_pool(db_session, 1)
        items = pack_main_line_plan_items(
            "A", line, pool, state, 90, "学者", carryover=[]
        )
        slots = {p["training_slot"] for p in items}
        assert len(slots) >= 2
        skills = [p.get("placeholder_skill") for p in items if p.get("placeholder_skill")]
        # 学者权重：高效作业 0.5 > 开口窍 0.4
        assert "高效作业" in skills or any(
            p.get("content_item_id") for p in items if p.get("training_slot") == 2
        )

    def test_120_min_three_items_two_rounds_reading(self, db_session, child_with_assessment):
        uid = child_with_assessment
        from app.db.models import ChildUser
        from app.services.child_training_state import get_training_progress

        child = db_session.get(ChildUser, uid)
        state = get_training_progress(child)
        cur = load_training_curriculum()
        line = cur["main_lines"]["A"]
        from app.services.talent_content_pool import get_talent_content_pool

        pool = get_talent_content_pool(db_session, 1)
        items = pack_main_line_plan_items(
            "A", line, pool, state, 120, "学者", carryover=[]
        )
        slots = {p["training_slot"] for p in items}
        assert len(slots) >= 3
        ph = [p.get("placeholder_skill") for p in items if p.get("placeholder_skill")]
        # 3 项时两项辅练/可选都应展示（开口窍占位 + 高效作业）
        assert "开口窍" in ph
        assert "高效作业" in ph or any(p.get("content_item_id") for p in items)

    def test_build_schedule_90_min(self, db_session, child_with_assessment):
        uid = child_with_assessment
        route = build_curriculum_schedule(
            db_session, uid, 1, 90, talent_primary="学者"
        )
        slots = {p.get("training_slot") for p in route["plan_items"]}
        assert 2 in slots
        assert "2 个训练块" in route["note"] or "2个训练块" in route["note"].replace(" ", "")
