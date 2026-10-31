# -*- coding: utf-8 -*-
"""P1 R8：进页主动节奏（掉队 / 连打 / 周简报）。"""

from app.agents.guide.context import GuideContext
from app.agents.guide.long_term import LongTermSummary
from app.agents.guide.proactive import (
    KIND_COMEBACK,
    KIND_STREAK,
    KIND_WEEKLY,
    resolve_proactive,
    save_proactive_state,
)


def _ctx(**kwargs) -> GuideContext:
    uid = int(kwargs.pop("child_user_id", 1))
    day = str(kwargs.pop("training_day", "2026-07-29"))
    allowed = {
        "nickname", "grade", "talent", "has_assessment",
        "days_since_last_checkin", "situation", "next_action",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    fields.setdefault("has_assessment", True)
    fields.setdefault("days_since_last_checkin", 1)
    fields.setdefault("situation", "ready_to_train")
    fields.setdefault("next_action", "train")
    return GuideContext(uid, day, **fields)


def test_proactive_disabled_by_env(db_session, monkeypatch):
    from app.services.auth_service import register_child

    monkeypatch.setenv("GUIDE_PROACTIVE_ENABLED", "0")
    user = register_child(db_session, parent_phone="1390000r801", nickname="关主动")
    ctx = _ctx(child_user_id=user.id, situation="sparse_return", days_since_last_checkin=5)
    ctx.situation = "sparse_return"
    assert resolve_proactive(db_session, user.id, ctx, LongTermSummary()) is None


def test_proactive_comeback(db_session, monkeypatch):
    from app.services.auth_service import register_child

    monkeypatch.setenv("GUIDE_PROACTIVE_ENABLED", "1")
    user = register_child(db_session, parent_phone="1390000r802", nickname="掉队")
    ctx = _ctx(child_user_id=user.id, days_since_last_checkin=5)
    ctx.situation = "sparse_return"
    got = resolve_proactive(db_session, user.id, ctx, LongTermSummary())
    assert got and got["kind"] == KIND_COMEBACK
    assert "回来" in got["text"]

    again = resolve_proactive(db_session, user.id, ctx, LongTermSummary())
    assert again and again.get("cached") is True
    assert again["text"] == got["text"]


def test_proactive_streak_milestone(db_session, monkeypatch):
    from app.services.auth_service import register_child

    monkeypatch.setenv("GUIDE_PROACTIVE_ENABLED", "1")
    monkeypatch.setenv("GUIDE_PROACTIVE_WEEKLY", "0")
    user = register_child(db_session, parent_phone="1390000r803", nickname="连打")
    ctx = _ctx(child_user_id=user.id)
    ctx.situation = "ready_to_train"
    lt = LongTermSummary(checkin_streak=7, total_checkins=7, checkins_last_14d=7)
    got = resolve_proactive(db_session, user.id, ctx, lt)
    assert got and got["kind"] == KIND_STREAK
    assert "7" in got["text"]


def test_proactive_weekly_once_per_iso_week(db_session, monkeypatch):
    from app.services.auth_service import register_child

    monkeypatch.setenv("GUIDE_PROACTIVE_ENABLED", "1")
    monkeypatch.setenv("GUIDE_PROACTIVE_WEEKLY", "1")
    user = register_child(db_session, parent_phone="1390000r804", nickname="周报")
    ctx = _ctx(child_user_id=user.id, training_day="2026-07-27")  # ISO week
    ctx.situation = "ready_to_train"
    lt = LongTermSummary(
        total_checkins=5,
        checkins_last_14d=4,
        preferred_minutes=30,
        weak_skills=["扫描速记"],
    )
    got = resolve_proactive(db_session, user.id, ctx, lt)
    assert got and got["kind"] == KIND_WEEKLY
    assert "本周小结" in got["text"]
    assert "扫描速记" in got["text"]

    # 同周另一天：因 shown_day 不同且 last_weekly_iso 已记，不应再发周报；
    # 也无 comeback/streak → None
    ctx2 = _ctx(child_user_id=user.id, training_day="2026-07-28")
    ctx2.situation = "ready_to_train"
    assert resolve_proactive(db_session, user.id, ctx2, lt) is None


def test_proactive_profile_disable(db_session, monkeypatch):
    from app.services.auth_service import register_child

    monkeypatch.setenv("GUIDE_PROACTIVE_ENABLED", "1")
    user = register_child(db_session, parent_phone="1390000r805", nickname="关档")
    save_proactive_state(db_session, user.id, {"enabled": False})
    ctx = _ctx(child_user_id=user.id)
    ctx.situation = "sparse_return"
    assert resolve_proactive(db_session, user.id, ctx, LongTermSummary()) is None
