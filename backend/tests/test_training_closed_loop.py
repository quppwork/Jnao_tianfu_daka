"""闭环：打卡进阶 + 规则排课"""

from app.services.child_training_state import save_training_progress
from app.services.training_mastery import _rule_met, evaluate_main_line_advance
from app.services.training_curriculum_scheduler import build_curriculum_schedule


def test_super_brain_reading_rule_detected():
    cards = [{"name": "超脑阅读", "time": "1", "content": "1200"}]
    assert _rule_met("超脑阅读_一分钟1000字", cards[0], "primary_low")
    cards_word_count = [{"name": "超脑阅读", "time": 1, "wordCount": 1000}]
    assert _rule_met("超脑阅读_一分钟1000字", cards_word_count[0], "primary_low")
    cards_fail = [{"name": "超脑阅读", "time": "1", "content": "200"}]
    assert _rule_met("超脑阅读_一分钟1000字", cards_fail[0], "primary_low") is False
    # 2分钟2000字，1:1000 比例达标
    cards_ratio = [{"name": "超脑阅读", "time": 2, "wordCount": 2000}]
    assert _rule_met("超脑阅读_一分钟1000字", cards_ratio[0], "primary_low")


def test_image_recall_grade_rule_uses_word_count():
    card = {"name": "影像追忆", "time": 5, "wordCount": 500}
    assert _rule_met("影像追忆_年级表", card, "primary_high")


def test_main_line_advance_enabled_when_reading_met():
    state = {"main_line": "A", "skills": {}, "main_line_sessions": 1}
    cards = [{"name": "超脑阅读", "time": 1, "wordCount": 1200}]
    assert evaluate_main_line_advance(state, cards, "primary_low") is True
    fail_cards = [{"name": "超脑阅读", "time": 1, "wordCount": 200}]
    assert evaluate_main_line_advance(state, fail_cards, "primary_low") is False


def test_advance_eval_returns_detail():
    from app.services.training_mastery import build_main_line_advance_eval

    state = {"main_line": "A", "skills": {}, "main_line_sessions": 0}
    cards = [{"name": "超脑阅读", "time": 1, "wordCount": 1000}]
    ev = build_main_line_advance_eval(state, cards, "primary_low")
    assert ev["advance_met"] is True
    assert ev["advance_detail"]["words_per_minute"] == 1000
    assert ev["main_line_to"] == "B"


def test_main_line_advance_reading_only_no_session_floor():
    """A→B 不要求累计训练次数，第 1 次打卡达标即可判定"""
    state = {"main_line": "A", "skills": {}, "main_line_sessions": 1}
    cards = [{"name": "超脑阅读", "time": "1", "content": "1200"}]
    assert evaluate_main_line_advance(state, cards, "primary_low") is True


def test_multi_round_advance_any_one_round_met():
    """多轮训练：同技能只要有一轮达标即可进阶"""
    from app.services.training_mastery import build_main_line_advance_eval

    state = {"main_line": "A", "skills": {}, "main_line_sessions": 0}
    fail_round = {"name": "超脑阅读", "time": 1, "wordCount": 200, "phaseBlock": "A"}
    pass_round = {"name": "超脑阅读", "time": 1, "wordCount": 1200, "phaseBlock": "B"}
    assert evaluate_main_line_advance(state, [fail_round], "primary_low") is False
    assert evaluate_main_line_advance(state, [fail_round, pass_round], "primary_low") is True
    ev = build_main_line_advance_eval(state, [fail_round, pass_round], "primary_low")
    assert ev["advance_met"] is True
    assert ev["advance_detail"]["words_per_minute"] == 1200


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


def test_process_checkin_defers_main_line_to_next_day(db_session, child_with_assessment):
    from app.db.models import ChildUser
    from app.services.child_training_state import get_training_progress, save_training_progress
    from app.services.training_mastery import process_checkin_progress
    from app.services.training_service import get_or_create_today_plan

    uid = child_with_assessment
    child = db_session.get(ChildUser, uid)
    save_training_progress(
        db_session, child, {"main_line": "A", "skills": {}, "main_line_sessions": 0}
    )
    plan_data = get_or_create_today_plan(db_session, uid)
    from app.db.models import TrainingPlan

    plan = db_session.get(TrainingPlan, plan_data["plan_id"])
    cards = [{"name": "超脑阅读", "time": 1, "wordCount": 1000}]
    delta = process_checkin_progress(
        db_session,
        child,
        plan,
        cards,
        talent_code=1,
        grade="三年级",
    )
    assert delta["advance_met"] is True
    assert delta["advance_pending"] is True
    assert delta["pending_main_line_to"] == "B"
    assert delta["main_line"] == "A"
    state = get_training_progress(child)
    assert state["main_line"] == "A"
    assert state["pending_main_line_to"] == "B"


def test_process_checkin_multi_round_any_one_met(db_session, child_with_assessment):
    from app.db.models import ChildUser, TrainingPlan
    from app.services.child_training_state import get_training_progress, save_training_progress
    from app.services.training_mastery import process_checkin_progress
    from app.services.training_service import get_or_create_today_plan, submit_checkin

    uid = child_with_assessment
    child = db_session.get(ChildUser, uid)
    save_training_progress(
        db_session, child, {"main_line": "A", "skills": {}, "main_line_sessions": 0}
    )
    plan_data = get_or_create_today_plan(db_session, uid)
    plan = db_session.get(TrainingPlan, plan_data["plan_id"])
    items = sorted(plan.items, key=lambda i: i.sort_order)
    assert items

    submit_checkin(
        db_session,
        uid,
        plan_id=plan.id,
        item_id=items[0].id,
        cards=[{"name": "超脑阅读", "time": 1, "wordCount": 200, "phaseBlock": "A"}],
    )
    db_session.commit()
    db_session.refresh(child)
    assert get_training_progress(child).get("pending_main_line_to") is None

    delta = process_checkin_progress(
        db_session,
        child,
        plan,
        [{"name": "超脑阅读", "time": 1, "wordCount": 1200, "phaseBlock": "B"}],
        talent_code=1,
        grade="三年级",
    )
    assert delta["advance_met"] is True
    assert delta["pending_main_line_to"] == "B"


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
