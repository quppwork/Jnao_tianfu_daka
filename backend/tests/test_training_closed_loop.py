"""闭环：打卡进阶 + 规则排课"""

from app.services.child_training_state import save_training_progress
from app.services.training_mastery import _rule_met, evaluate_main_line_advance
from app.services.training_curriculum_scheduler import build_curriculum_schedule


def test_super_brain_reading_rule_detected():
    cards = [{"name": "超脑阅读", "time": "1", "content": "1200"}]
    assert _rule_met("超脑阅读_一分钟1000字", cards[0], "primary_low")
    cards_fail = [{"name": "超脑阅读", "time": "1", "content": "200"}]
    assert _rule_met("超脑阅读_一分钟1000字", cards_fail[0], "primary_low") is False


def test_main_line_advance_enabled_when_reading_met():
    state = {"main_line": "A", "skills": {}, "main_line_sessions": 1}
    cards = [{"name": "超脑阅读", "time": "1", "content": "1200"}]
    assert evaluate_main_line_advance(state, cards, "primary_low") is True
    fail_cards = [{"name": "超脑阅读", "time": "1", "content": "200"}]
    assert evaluate_main_line_advance(state, fail_cards, "primary_low") is False


def test_main_line_advance_reading_only_no_session_floor():
    """A→B 不要求累计训练次数，第 1 次打卡达标即可判定"""
    state = {"main_line": "A", "skills": {}, "main_line_sessions": 1}
    cards = [{"name": "超脑阅读", "time": "1", "content": "1200"}]
    assert evaluate_main_line_advance(state, cards, "primary_low") is True


def test_scheduler_first_schedule(db_session, child_with_assessment):
    from app.db.models import ChildUser
    from app.services.assessment_service import effective_talent_code, get_latest_assessment

    uid = child_with_assessment
    child = db_session.get(ChildUser, uid)
    save_training_progress(
        db_session, child, {"main_line": "A", "skills": {}, "main_line_sessions": 0}
    )
    code = effective_talent_code(get_latest_assessment(db_session, uid))
    route = build_curriculum_schedule(
        db_session, uid, code, 45, content_index=0, talent_primary="学者"
    )
    assert route.get("plan_items")
    assert route["mode"] in ("curriculum_day_one", "curriculum_loop")


def test_scheduler_main_line_b_after_advance(db_session, child_with_assessment):
    from app.db.models import ChildUser
    from app.services.assessment_service import effective_talent_code, get_latest_assessment

    uid = child_with_assessment
    child = db_session.get(ChildUser, uid)
    save_training_progress(
        db_session,
        child,
        {"main_line": "B", "skills": {}, "main_line_sessions": 1},
    )
    code = effective_talent_code(get_latest_assessment(db_session, uid))
    route = build_curriculum_schedule(
        db_session, uid, code, 45, content_index=1, talent_primary="学者"
    )
    assert route.get("plan_items")
    assert route.get("main_line") == "B"
    slots = {int(r.get("training_slot") or 1) for r in route["plan_items"]}
    assert 1 in slots
