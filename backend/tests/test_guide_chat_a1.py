# -*- coding: utf-8 -*-
"""首页引导 A1：对话注入情境 + 历史截断"""

from app.agents.guide.memory import truncate_history
from app.agents.guide.runner import HISTORY_MAX_TURNS, build_chat_system_prompt, prepare_history
from app.services.auth_service import register_child


def test_truncate_history_keeps_tail():
    msgs = [{"role": "user", "content": str(i)} for i in range(20)]
    out = truncate_history(msgs, max_turns=5)
    assert len(out) == 5
    assert out[0]["content"] == "15"
    assert out[-1]["content"] == "19"


def test_prepare_history_uses_default_cap():
    msgs = [{"role": "user", "content": str(i)} for i in range(HISTORY_MAX_TURNS + 5)]
    out = prepare_history(msgs)
    assert len(out) == HISTORY_MAX_TURNS


def test_build_chat_system_includes_context(db_session):
    user = register_child(db_session, parent_phone="1390000a101", nickname="情境注入")
    prompt = build_chat_system_prompt(db_session, user.id)
    assert "学生情境" in prompt
    assert "已测评" in prompt
    assert "判定情境" in prompt
    assert "张宇老师" in prompt
