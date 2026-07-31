# -*- coding: utf-8 -*-
"""QA P1：滚动摘要 / 弱澄清 / 回归 fixture / trace。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.qa.clarify import clarification_reply, needs_stem_clarification
from app.agents.qa.eval_safety import eval_clarify_reply, scan_qa_leaks
from app.agents.qa.memory import (
    QaMemory,
    fold_overflow_history,
    load_session_memory,
    memory_to_prompt_block,
    save_session_memory,
)
from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.agents.qa.router import check_subject_mismatch
from app.agents.qa.trace import (
    TurnTimer,
    build_qa_turn_trace,
    emit_qa_trace,
    get_qa_trace_metrics,
    reset_qa_trace_metrics,
)
from app.db.models import QaSession
from app.services.qa_rag_router import should_use_rag

_FIXTURE = Path(__file__).parent / "fixtures" / "qa_p1_regression.json"


def _load() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_qa_trace_metrics()
    yield
    reset_qa_trace_metrics()


@pytest.mark.parametrize("case", _load()["mismatch"], ids=lambda c: c["id"])
def test_p1_mismatch_fixture(case):
    m = check_subject_mismatch(case["message"], case["selected_subject"])
    assert m is not None, case
    assert m.detected == case["expect_detected"]


@pytest.mark.parametrize("case", _load()["clarify"], ids=lambda c: c["id"])
def test_p1_clarify_fixture(case):
    got = needs_stem_clarification(
        case["message"],
        has_image=bool(case.get("has_image")),
        has_prior_turns=bool(case.get("has_prior_turns")),
    )
    assert got is case["expect_clarify"], case


@pytest.mark.parametrize("case", _load()["safety"], ids=lambda c: c["id"])
def test_p1_safety_leak_scanner(case):
    assert scan_qa_leaks(case["bad_reply"]), case
    assert not scan_qa_leaks(case["good_reply"]), case


@pytest.mark.parametrize("case", _load()["ocr_rag_boundary"], ids=lambda c: c["id"])
def test_p1_rag_boundary(case):
    got = should_use_rag(case["message"], has_image=bool(case.get("has_image")))
    assert got is case["expect_rag"], case


@pytest.mark.parametrize("case", _load()["clarify_reply"], ids=lambda c: c["id"])
def test_p1_clarify_reply_eval(case):
    got = eval_clarify_reply(case["reply"])
    assert got["ok"] is case["expect_ok"], case


def test_p1_clarification_reply_asks_stem():
    assert eval_clarify_reply(clarification_reply())["ok"] is True


def test_fold_overflow_builds_summary():
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(14)]
    recent, mem = fold_overflow_history(msgs, {}, keep=10)
    assert len(recent) == 10
    assert "学员:msg0" in mem["rolling_summary"]
    assert "老师:msg1" in mem["rolling_summary"]
    block = memory_to_prompt_block(mem)
    assert "近期本题对话摘要" in block
    prompt = build_qa_system_prompt(subject="数学", memory_digest=block)
    assert "近期本题对话摘要" in prompt


def test_session_memory_cleared_on_delete(db_session, registered_user):
    from app.services import qa_service

    uid = registered_user["child_user_id"]
    session = qa_service.create_session(db_session, uid, "数学")
    save_session_memory(
        db_session,
        session,
        {"rolling_summary": "学员:旧题；老师:讲解"},
    )
    db_session.commit()
    assert "旧题" in load_session_memory(session)["rolling_summary"]

    ok = qa_service.delete_session(db_session, session.id, uid)
    assert ok is True
    assert db_session.get(QaSession, session.id) is None


def test_prepare_history_and_digest_persists(db_session, registered_user):
    from app.db.models import QaMessage
    from app.services import qa_service

    uid = registered_user["child_user_id"]
    session = qa_service.create_session(db_session, uid, "数学")
    for i in range(14):
        db_session.add(
            QaMessage(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"轮次内容{i}分数",
            )
        )
    db_session.commit()
    db_session.refresh(session)

    history, digest = QaMemory.prepare_history_and_digest(db_session, session, keep=10)
    db_session.commit()
    db_session.refresh(session)
    assert len(history) == 10
    assert digest
    assert "近期本题对话摘要" in digest
    assert load_session_memory(session)["rolling_summary"]


def test_qa_trace_metrics():
    t = TurnTimer()
    emit_qa_trace(
        build_qa_turn_trace(
            child_user_id=1,
            session_id=2,
            subject="数学",
            message="不会",
            duration_ms=t.ms(),
            reply="请发题干",
            clarified=True,
        )
    )
    m = get_qa_trace_metrics()
    assert m["turns"] == 1
    assert m["clarify_turns"] == 1


def test_qa_clarify_api_no_llm(client, child_with_assessment, mock_doubao):
    uid = child_with_assessment
    res = client.post(
        f"/api/qa/chat?user_id={uid}",
        json={"message": "你好", "subject": "数学"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("clarified") is True
    assert "题干" in data["reply"] or "拍照" in data["reply"]
    assert mock_doubao["chat"].call_count == 0
