# -*- coding: utf-8 -*-
"""Guide Agent 阶段 C：评测抽检 + 长期摘要 + 日快照缓存。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.agents.guide.context import GuideContext, TodayPlanSnapshot
from app.agents.guide.long_term import (
    LongTermSummary,
    build_daily_snapshot,
    build_long_term_summary,
)
from app.agents.guide.memory import clear_bootstrap_cache, get_cached_welcome
from app.agents.guide.runner import build_chat_system_prompt
from app.agents.guide.situations import resolve_situation, template_welcome
from app.db.models import TrainingPlan, TrainingRecord
from app.services.auth_service import register_child
from app.services.child_training_state import (
    get_training_progress,
    save_training_progress,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "guide_eval_cases.json"


def _eval_cases() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return data["cases"]


def _ctx_for_case(case_id: str) -> GuideContext:
    base = GuideContext(1, "2026-07-23", has_assessment=True, nickname="评测")
    if case_id == "need_assessment":
        base.has_assessment = False
        return base
    if case_id == "ready_to_train":
        base.days_since_last_checkin = 1
        return base
    if case_id == "sparse_return":
        base.days_since_last_checkin = 5
        return base
    if case_id == "training_in_progress":
        base.today = TodayPlanSnapshot(
            exists=True,
            item_count=2,
            done_count=0,
            has_started=True,
            status="pending",
        )
        return base
    if case_id == "training_done":
        base.today = TodayPlanSnapshot(
            exists=True,
            item_count=2,
            done_count=2,
            has_started=True,
            status="completed",
        )
        return base
    raise ValueError(case_id)


@pytest.mark.parametrize("case", _eval_cases(), ids=lambda c: c["id"])
def test_eval_resolve_situation(case):
    ctx = _ctx_for_case(case["id"])
    assert resolve_situation(ctx) == (case["situation"], case["next_action"])


@pytest.mark.parametrize("case", _eval_cases(), ids=lambda c: c["id"])
def test_eval_template_welcome_keywords(case):
    text = template_welcome(case["situation"], nickname="小测")
    for kw in case["welcome_keywords"]:
        assert kw in text, f"{case['id']}: expect `{kw}` in `{text}`"


@pytest.mark.asyncio
async def test_bootstrap_snapshot_cached(db_session):
    clear_bootstrap_cache()
    user = register_child(db_session, parent_phone="1390000c001", nickname="快照童")
    from app.services import guide_service

    first = await guide_service.bootstrap(
        db_session, user.id, force=True, use_llm=False
    )
    assert first["situation"] == "need_assessment"
    assert first["source"] == "template"
    snap = first.get("snapshot") or {}
    assert snap.get("has_assessment") is False
    assert snap.get("situation") == "need_assessment"
    assert snap.get("next_action") == "talent"

    again = await guide_service.bootstrap(
        db_session, user.id, force=False, use_llm=False
    )
    assert again["source"] == "cache"
    assert again.get("snapshot")
    cached = get_cached_welcome(db_session, user.id, first["training_day"])
    assert cached and cached.get("snapshot")


def test_long_term_empty_without_checkins(db_session):
    user = register_child(db_session, parent_phone="1390000c002", nickname="空摘要")
    lt = build_long_term_summary(db_session, user.id, training_day=date(2026, 7, 23))
    assert lt.total_checkins == 0
    assert lt.checkin_streak == 0
    assert lt.weak_skills == []
    assert lt.to_prompt_block() == ""


def test_long_term_weak_skills_and_minutes(db_session):
    user = register_child(db_session, parent_phone="1390000c003", nickname="弱项童")
    today = date(2026, 7, 23)
    for d in (today - timedelta(days=1), today):
        db_session.add(
            TrainingRecord(child_user_id=user.id, train_date=d, ability_type="影像追忆")
        )
    for mins, offset in ((40, 2), (40, 3), (20, 4)):
        db_session.add(
            TrainingPlan(
                child_user_id=user.id,
                plan_date=today - timedelta(days=offset),
                planned_minutes=mins,
                status="completed",
            )
        )
    state = get_training_progress(user)
    state["training_days"] = 2
    state["skills"]["影像追忆"]["tier"] = 1
    state["skills"]["扫描速记"]["tier"] = 3
    state["skills"]["极速运算"]["tier"] = 2
    save_training_progress(db_session, user, state)
    flag_modified(user, "profile_json")
    db_session.commit()

    lt = build_long_term_summary(db_session, user.id, training_day=today)
    assert lt.total_checkins == 2
    assert lt.checkin_streak >= 1
    assert lt.preferred_minutes == 40
    assert "影像追忆" in lt.weak_skills
    block = lt.to_prompt_block()
    assert "长期摘要" in block
    assert "影像追忆" in block


def test_build_chat_system_includes_long_term(db_session):
    user = register_child(db_session, parent_phone="1390000c004", nickname="注入童")
    today = date(2026, 7, 23)
    db_session.add(
        TrainingRecord(child_user_id=user.id, train_date=today, ability_type="扫描速记")
    )
    state = get_training_progress(user)
    state["training_days"] = 1
    state["skills"]["扫描速记"]["tier"] = 1
    state["skills"]["极速学习"]["tier"] = 4
    save_training_progress(db_session, user, state)
    flag_modified(user, "profile_json")
    db_session.commit()

    prompt = build_chat_system_prompt(db_session, user.id)
    assert "长期摘要（DB）" in prompt
    assert "扫描速记" in prompt or "累计打卡" in prompt


def test_daily_snapshot_shape():
    ctx = GuideContext(
        1,
        "2026-07-23",
        has_assessment=True,
        days_since_last_checkin=2,
        situation="ready_to_train",
        next_action="train",
    )
    ctx.today = TodayPlanSnapshot(exists=True, has_started=False, status="pending")
    lt = LongTermSummary(
        checkin_streak=3,
        checkins_last_14d=5,
        weak_skills=["影像追忆"],
        preferred_minutes=40,
        total_checkins=10,
    )
    snap = build_daily_snapshot(ctx, lt)
    assert snap["has_assessment"] is True
    assert snap["days_since_last_checkin"] == 2
    assert snap["today_started"] is False
    assert snap["long_term"]["preferred_minutes"] == 40
    assert snap["long_term"]["weak_skills"] == ["影像追忆"]


def test_empty_long_term_omitted_from_snapshot():
    ctx = GuideContext(1, "2026-07-23", situation="need_assessment", next_action="talent")
    snap = build_daily_snapshot(ctx, LongTermSummary())
    assert "long_term" not in snap
