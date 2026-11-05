"""家长训练看板 · 冲段焦虑与 dashboard 形态。"""

from datetime import date, timedelta

from app.services.parent_dashboard_service import compute_anxiety, day_efficiency


def test_anxiety_triggers_when_high_then_decline():
    today = date(2026, 9, 12)
    series = [
        (today - timedelta(days=2), 92.0),
        (today - timedelta(days=1), 88.0),
        (today, 83.0),
    ]
    ax = compute_anxiety(series)
    assert ax["active"] is True
    assert ax["level"] == "warn"
    assert ax["value"] == 83
    assert ax["peak"] == 92


def test_anxiety_off_when_never_high():
    today = date(2026, 9, 12)
    series = [
        (today - timedelta(days=2), 70.0),
        (today - timedelta(days=1), 68.0),
        (today, 65.0),
    ]
    ax = compute_anxiety(series)
    assert ax["active"] is False


def test_anxiety_off_when_rising():
    today = date(2026, 9, 12)
    series = [
        (today - timedelta(days=2), 91.0),
        (today - timedelta(days=1), 93.0),
        (today, 95.0),
    ]
    ax = compute_anxiety(series)
    assert ax["active"] is False


def test_day_efficiency_prefers_attitude():
    class R:
        def __init__(self, a):
            self.attitude_pct = a

    assert day_efficiency([R(90), R(80)], None) == 85.0


def test_match_and_clarify_helpers():
    from app.services.parent_guide_service import (
        match_child_from_message,
        needs_child_clarification,
    )

    kids = [
        {"id": 1, "nickname": "小明"},
        {"id": 2, "nickname": "小红"},
    ]
    assert match_child_from_message("看看小明的报告", kids) == 1
    assert needs_child_clarification("孩子的报告怎么样", kids, child_id=None) is True
    assert needs_child_clarification("小明的报告怎么样", kids, child_id=None) is False
    assert needs_child_clarification("家长课程有哪些", kids, child_id=None) is False
    assert needs_child_clarification("孩子的报告怎么样", kids, child_id=1) is False
    assert needs_child_clarification("先看哪个孩子", kids, child_id=1) is True
