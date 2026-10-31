# -*- coding: utf-8 -*-
"""R10：个性化策略层（天赋 / 弱项 / 情境）。"""

from app.agents.guide.context import GuideContext
from app.agents.guide.long_term import LongTermSummary
from app.agents.guide.strategy import (
    TALENT_STRATEGY,
    resolve_strategy,
    strategy_to_prompt_block,
)


def test_strategy_talent_and_situation():
    ctx = GuideContext(
        1,
        "2026-07-30",
        talent="学者",
        has_assessment=True,
        situation="ready_to_train",
        next_action="train",
    )
    s = resolve_strategy(ctx, LongTermSummary())
    assert "talent:学者" in s["keys"]
    assert "situation:ready_to_train" in s["keys"]
    block = strategy_to_prompt_block(s)
    assert "学者" in block
    assert "可开练" in block or "开练" in block
    assert "禁止解释" in block or "晋级" in block


def test_strategy_weak_skills():
    ctx = GuideContext(
        1,
        "2026-07-30",
        talent="德者",
        situation="sparse_return",
        next_action="train",
        has_assessment=True,
    )
    lt = LongTermSummary(weak_skills=["扫描速记", "超脑阅读"], total_checkins=5)
    s = resolve_strategy(ctx, lt)
    assert any(k.startswith("weak:") for k in s["keys"])
    assert "扫描速记" in strategy_to_prompt_block(s)
    assert "德者" in strategy_to_prompt_block(s)
    assert "掉队" in strategy_to_prompt_block(s) or "欢迎" in strategy_to_prompt_block(s)


def test_strategy_disabled(monkeypatch):
    monkeypatch.setenv("GUIDE_STRATEGY_ENABLED", "0")
    ctx = GuideContext(1, "2026-07-30", talent="赢者", situation="ready_to_train")
    s = resolve_strategy(ctx, LongTermSummary())
    assert s["lines"] == []
    assert strategy_to_prompt_block(s) == ""


def test_strategy_talent_from_display_string():
    ctx = GuideContext(
        1,
        "2026-07-30",
        talent="主天赋：赢者（锁定）",
        situation="training_done",
        has_assessment=True,
    )
    s = resolve_strategy(ctx, None)
    assert "talent:赢者" in s["keys"]
    assert "闯关" in strategy_to_prompt_block(s) or "赢者" in strategy_to_prompt_block(s)


def test_all_talents_have_strategy():
    for name in ("学者", "思者", "行者", "德者", "赢者"):
        assert name in TALENT_STRATEGY
        assert len(TALENT_STRATEGY[name]) > 10


def test_build_chat_system_includes_strategy(db_session, monkeypatch):
    monkeypatch.setenv("GUIDE_STRATEGY_ENABLED", "1")
    from app.agents.guide.runner import build_chat_system_prompt
    from app.services.assessment_service import save_assessment
    from app.services.auth_service import register_child

    user = register_child(db_session, parent_phone="1390000r101", nickname="策略童")
    save_assessment(
        db_session,
        child_user_id=user.id,
        jnao_record_id=f"r10-{user.id}",
        answer_bitstring="1" * 35,
        test_type=1,
        report={"talent": "行者", "create_time": "2026-06-18"},
    )
    prompt = build_chat_system_prompt(db_session, user.id)
    assert "个性化策略" in prompt
    assert "行者" in prompt or "动手" in prompt
