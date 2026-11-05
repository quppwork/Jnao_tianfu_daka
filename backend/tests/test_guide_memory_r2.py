# -*- coding: utf-8 -*-
"""R2 对话记忆：滚动摘要 + 结构化资产"""

from app.agents.guide.student_memory import (
    clear_guide_memory,
    extract_from_user_message,
    fold_overflow_history,
    load_guide_memory,
    save_guide_memory,
    to_prompt_block,
)
from app.agents.guide.runner import build_chat_system_prompt
from app.services.auth_service import register_child


def test_extract_preferred_minutes_and_focus():
    mem = extract_from_user_message("我想练40分钟，超脑阅读是弱项吗？", {})
    assert mem["preferences"].get("preferred_minutes") == 40
    assert "超脑阅读" in mem["recent_focus"]
    assert "弱项" in mem["recent_focus"]
    assert mem["open_intents"]


def test_fold_overflow_builds_digest():
    msgs = [
        {"role": "user", "content": f"问题{i}"}
        for i in range(15)
    ]
    recent, mem = fold_overflow_history(msgs, {}, keep=12)
    assert len(recent) == 12
    assert "学员:问题0" in mem["rolling_summary"] or "问题0" in mem["rolling_summary"]
    assert recent[0]["content"] == "问题3"


def test_to_prompt_block_and_persist(db_session):
    user = register_child(db_session, parent_phone="1390000m201", nickname="记忆童")
    mem = extract_from_user_message("我想练30分钟，下次还想问晋级", {})
    save_guide_memory(db_session, user.id, mem)
    loaded = load_guide_memory(db_session, user.id)
    assert loaded["preferences"]["preferred_minutes"] == 30
    block = to_prompt_block(loaded)
    assert "意向时长" in block
    assert "30" in block

    prompt = build_chat_system_prompt(
        db_session, user.id, memory_block=block
    )
    assert "对话记忆" in prompt
    assert "30" in prompt

    clear_guide_memory(db_session, user.id)
    assert not load_guide_memory(db_session, user.id).get("preferences")


def test_prepare_memory_folds_and_saves(db_session):
    from app.agents.guide.runner import _prepare_memory_and_history

    user = register_child(db_session, parent_phone="1390000m202", nickname="折叠童")
    history = [{"role": "user", "content": f"旧话{i}"} for i in range(14)]
    hist, block = _prepare_memory_and_history(
        db_session, user.id, "我想练25分钟", history
    )
    assert len(hist) <= 12
    assert "25" in block or "意向" in block
    loaded = load_guide_memory(db_session, user.id)
    assert loaded["preferences"].get("preferred_minutes") == 25
    assert loaded.get("rolling_summary")
