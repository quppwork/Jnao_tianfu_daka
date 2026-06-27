"""训练块：每块一项；主线 B 块1影像追忆、块2超脑阅读"""

from app.services.child_training_state import get_training_progress, save_training_progress
from app.services.training_block_builder import build_main_line_block_plan
from app.services.talent_content_pool import get_talent_content_pool
from config.loader import load_training_curriculum


class TestMainLineBBlocks:
    def test_b_blocks_one_item_per_slot(self, db_session, child_with_assessment):
        from app.db.models import ChildUser

        uid = child_with_assessment
        child = db_session.get(ChildUser, uid)
        save_training_progress(
            db_session,
            child,
            {"main_line": "B", "skills": {}, "main_line_sessions": 1},
        )
        pool = get_talent_content_pool(db_session, 1)
        line = load_training_curriculum()["main_lines"]["B"]
        state = get_training_progress(child)
        packed = build_main_line_block_plan(
            "B", line, pool, state, 90, "学者"
        )
        items = packed["plan_items"]
        slots = sorted({i["training_slot"] for i in items})
        assert slots[:2] == [1, 2]
        slot1 = [i for i in items if i["training_slot"] == 1]
        slot2 = [i for i in items if i["training_slot"] == 2]
        assert len(slot1) == 1
        assert len(slot2) == 1
        assert not any(
            i.get("item_type") == "perception" or i.get("placeholder_skill") == "感知力"
            for i in slot2
        )


class TestMainLineAOptionalOffers:
    def test_30_minutes_one_block_one_item(self, db_session, child_with_assessment):
        from app.db.models import ChildUser

        uid = child_with_assessment
        child = db_session.get(ChildUser, uid)
        save_training_progress(
            db_session,
            child,
            {"main_line": "A", "skills": {}, "main_line_sessions": 1},
        )
        pool = get_talent_content_pool(db_session, 1)
        line = load_training_curriculum()["main_lines"]["A"]
        state = get_training_progress(child)
        packed = build_main_line_block_plan(
            "A", line, pool, state, 30, "学者"
        )
        items = packed["plan_items"]
        assert len(items) == 1
        assert items[0]["training_slot"] == 1
        assert items[0].get("item_type") != "perception"
        assert items[0].get("placeholder_skill") != "感知力"

    def test_normalize_stacks_in_one_slot(self):
        from app.services.training_block_builder import normalize_plan_items_by_duration

        raw = [
            {"content_item_id": 1, "training_slot": 1, "role": "primary"},
            {"placeholder_skill": "感知力", "training_slot": 1, "role": "primary"},
            {"content_item_id": 2, "training_slot": 1, "role": "primary"},
        ]
        out = normalize_plan_items_by_duration(raw, 30)
        assert len(out) == 1
        assert out[0]["training_slot"] == 1

    def test_optional_not_in_plan_items(self, db_session, child_with_assessment):
        from app.db.models import ChildUser

        uid = child_with_assessment
        child = db_session.get(ChildUser, uid)
        save_training_progress(
            db_session,
            child,
            {"main_line": "A", "skills": {}, "main_line_sessions": 1},
        )
        pool = get_talent_content_pool(db_session, 1)
        line = load_training_curriculum()["main_lines"]["A"]
        state = get_training_progress(child)
        packed = build_main_line_block_plan(
            "A", line, pool, state, 90, "思者"
        )
        items = packed["plan_items"]
        skills = set()
        for it in items:
            if it.get("placeholder_skill"):
                skills.add(it["placeholder_skill"])
        assert "高效作业" not in skills
        assert "开口窍" not in skills
        offers = packed.get("optional_offers") or []
        assert offers
        top = offers[0]
        assert top["skill"] == "高效作业"
        assert top["suggested"]
        assert top["status"] == "pending"

    def test_one_item_per_slot_reading_then_perception(self, db_session, child_with_assessment):
        from app.db.models import ChildUser

        uid = child_with_assessment
        child = db_session.get(ChildUser, uid)
        save_training_progress(
            db_session,
            child,
            {"main_line": "A", "skills": {}, "main_line_sessions": 1},
        )
        pool = get_talent_content_pool(db_session, 1)
        line = load_training_curriculum()["main_lines"]["A"]
        state = get_training_progress(child)
        packed = build_main_line_block_plan(
            "A", line, pool, state, 90, "学者"
        )
        items = packed["plan_items"]
        slot1 = [i for i in items if i["training_slot"] == 1]
        slot2 = [i for i in items if i["training_slot"] == 2]
        assert len(slot1) == 1
        assert len(slot2) == 1
        assert not any(i.get("item_type") == "perception" for i in slot1)
        assert slot2[0].get("item_type") == "perception" or slot2[0].get("placeholder_skill") == "感知力"
