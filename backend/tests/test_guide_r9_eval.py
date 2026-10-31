# -*- coding: utf-8 -*-
"""R9：四类回归集 + 回合 trace 指标。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.guide.eval_safety import (
    eval_answer_then_guide,
    eval_grounding_numbers,
    scan_guide_leaks,
)
from app.agents.guide.persona import SYSTEM_PROMPT
from app.agents.guide.tools.planner import plan_tools_heuristic
from app.agents.guide.tools.query_normalize import normalize_guide_query
from app.agents.guide.trace import (
    TurnTimer,
    build_turn_trace,
    emit_guide_trace,
    get_guide_trace_metrics,
    reset_guide_trace_metrics,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "guide_r9_regression.json"


def _load() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_guide_trace_metrics()
    yield
    reset_guide_trace_metrics()


@pytest.mark.parametrize(
    "case",
    _load()["tool_routing"],
    ids=lambda c: c["id"],
)
def test_r9_tool_routing_heuristic(case):
    msg = normalize_guide_query(case["message"]) or case["message"]
    picks = plan_tools_heuristic(msg)
    names = {p["name"] for p in picks}
    expect = set(case["expect_tools_any"])
    assert names & expect, f"{case['id']}: got {names}, expect any of {expect}"


@pytest.mark.parametrize(
    "case",
    _load()["red_team"],
    ids=lambda c: c["id"],
)
def test_r9_red_team_leak_scanner(case):
    assert scan_guide_leaks(case["bad_reply"]), f"{case['id']}: bad_reply should leak"
    assert not scan_guide_leaks(case["good_reply"]), f"{case['id']}: good_reply clean"


def test_r9_persona_has_soft_mask_and_answer_first():
    assert "先答后导" in SYSTEM_PROMPT
    assert "模糊化" in SYSTEM_PROMPT or "晋级" in SYSTEM_PROMPT
    assert "Part" in SYSTEM_PROMPT or "达标" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    "case",
    _load()["answer_then_guide"],
    ids=lambda c: c["id"],
)
def test_r9_answer_then_guide(case):
    got = eval_answer_then_guide(case["reply"])
    assert got["ok"] is case["expect_ok"], case


@pytest.mark.parametrize(
    "case",
    _load()["grounding"],
    ids=lambda c: c["id"],
)
def test_r9_grounding_numbers(case):
    got = eval_grounding_numbers(
        case["reply"],
        tool_block=case.get("tool_block") or "",
    )
    assert got["ok"] is case["expect_ok"], case


def test_r9_skill_progress_tool_no_internal_counters(db_session):
    from app.agents.guide.tools.skill_progress import get_skill_progress
    from app.services.auth_service import register_child
    from app.services.child_training_state import get_training_progress, save_training_progress
    from sqlalchemy.orm.attributes import flag_modified

    user = register_child(db_session, parent_phone="1390000r901", nickname="R9档位")
    state = get_training_progress(user)
    state["training_days"] = 3
    state["skills"]["超脑阅读"]["tier"] = 2
    state["skills"]["超脑阅读"]["consecutive_pass"] = 2
    state["skills"]["超脑阅读"]["part"] = 2
    state["skills"]["超脑阅读"]["part_listen_count"] = 9
    save_training_progress(db_session, user, state)
    flag_modified(user, "profile_json")
    db_session.commit()

    out = get_skill_progress(db_session, user.id, {})
    blob = json.dumps(out, ensure_ascii=False)
    assert "consecutive_pass" not in blob
    assert "part_listen" not in blob
    assert scan_guide_leaks(blob) == []
    assert out["skills"]["超脑阅读"]["tier"] == 2


def test_r9_trace_metrics_and_empty_rate():
    timer = TurnTimer()
    t1 = build_turn_trace(
        child_user_id=1,
        message="今天练了吗",
        tools_used=[{"name": "get_today_plan", "ok": True, "round": 0}],
        duration_ms=timer.ms() + 12,
        situation="ready_to_train",
        next_action="train",
        reply="今日有方案",
    )
    emit_guide_trace(t1)
    t2 = build_turn_trace(
        child_user_id=1,
        message="你好",
        tools_used=[],
        duration_ms=5,
        reply="你好",
    )
    emit_guide_trace(t2)
    m = get_guide_trace_metrics()
    assert m["turns"] == 2
    assert m["empty_tools_turns"] == 1
    assert m["empty_tool_rate"] == 0.5
    assert m["tool_calls"] == 1


def test_r9_debug_includes_trace_metrics(client, monkeypatch):
    monkeypatch.setenv("JNAO_DEBUG_ROUTES", "1")
    # 兼容不同 debug 开关名
    from app.core import security

    monkeypatch.setattr(security, "is_debug_routes_enabled", lambda: True)
    emit_guide_trace(
        build_turn_trace(
            child_user_id=9,
            message="x",
            tools_used=[],
            duration_ms=1,
        )
    )
    res = client.get("/api/guide/debug")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "trace_metrics" in data
    assert data["trace_metrics"]["turns"] >= 1
