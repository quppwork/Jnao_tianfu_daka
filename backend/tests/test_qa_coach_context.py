import pytest
# -*- coding: utf-8 -*-
"""答疑 coach_hint / mistake_pattern 跨轮复用"""

from app.db.models import QaMessage, QaSession
from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.services.qa_coach import fetch_recent_coach_context_for_prompt


def test_fetch_recent_coach_context_from_meta(db_session, registered_user):
    child_user_id = registered_user["child_user_id"]
    session = QaSession(child_user_id=child_user_id, title="数学")
    db_session.add(session)
    db_session.flush()
    db_session.add(
        QaMessage(
            session_id=session.id,
            role="assistant",
            content="先列已知条件",
            meta_json={
                "coach_hint": "思者型：先写步骤再算",
                "mistake_pattern": "overthink",
            },
        )
    )
    db_session.commit()

    ctx = fetch_recent_coach_context_for_prompt(db_session, child_user_id, session_id=session.id)
    assert ctx
    assert "想太多" in ctx
    assert "思者型" in ctx

    prompt = build_qa_system_prompt(subject="数学", coach_context=ctx)
    assert "想太多" in prompt
