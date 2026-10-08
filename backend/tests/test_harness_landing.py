"""Harness 落地：家长脱钩、交接包、内核四件套。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.shared.handoff import make_handoff_packet, resolve_reply_actions
from app.harness.llm import PROFILES, profile_system, route
from app.harness.memory import fold_and_truncate, truncate_history
from app.harness.registry import reset_registry_for_tests
from app.harness.runtime import call_tool
from app.harness.trace import clear_for_tests, recent
from app.services import auth_service


@pytest.fixture(autouse=True)
def _reset():
    reset_registry_for_tests()
    clear_for_tests()
    yield
    reset_registry_for_tests()
    clear_for_tests()


def test_profiles_cover_facades():
    for name in ("consult", "guide", "parent_guide", "qa", "academy", "harness"):
        assert profile_system(name)
        assert name in PROFILES
    # 架构图别名
    assert profile_system("guide_child") == profile_system("guide")
    assert profile_system("guide_parent") == profile_system("parent_guide")
    # 人设/知识在 PROFILES（LLM 路由层）
    consult = PROFILES["consult"]
    assert consult.get("knowledge", {}).get("docs")
    assert "sizhe" in (consult.get("personas") or {})
    assert "脑科学" in profile_system("consult", persona="sizhe")
    # 流式入口在 route().stream（透传，非 SSE）
    assert hasattr(route("consult"), "stream")
    assert hasattr(route("consult"), "complete")


def test_truncate_and_fold():
    msgs = [{"role": "user", "content": f"m{i}"} for i in range(20)]
    tail = truncate_history(msgs, max_turns=5)
    assert len(tail) == 5
    recent_msgs, mem = fold_and_truncate(msgs, {}, keep=4)
    assert len(recent_msgs) == 4
    assert mem.get("rolling_summary")


def test_window_keeps_system_and_folds_rest():
    from app.harness.memory import window_for_model

    msgs = [{"role": "system", "content": "sys"}] + [
        {"role": "user", "content": f"m{i}"} for i in range(30)
    ]
    window, mem = window_for_model(msgs, {}, keep=6)
    assert window[0]["role"] == "system"
    assert "sys" in str(window[0]["content"])
    assert len(window) == 7
    assert mem.get("rolling_summary")


def test_qa_handoff_packet_keeps_context():
    pkt = make_handoff_packet(
        intent="qa",
        message="我有数学题不会做：3x+1=7",
        child_id=42,
        image_id="img-9",
    )
    assert pkt["from"] == "guide"
    assert pkt["subject"] == "数学"
    assert pkt["child_id"] == "42"
    assert pkt["image"] == "img-9"
    assert "3x+1=7" in pkt["query"]
    from app.harness.orchestration import ORCHESTRATION_MODE, handoff_packet

    assert ORCHESTRATION_MODE == "handoff_packet"
    assert handoff_packet(
        intent="qa",
        message="我有数学题不会做：3x+1=7",
        child_id=42,
        image_id="img-9",
    ) == pkt
    acts = resolve_reply_actions(
        situation_next="train",
        message="我有数学题不会做：3x+1=7",
        child_id=42,
        has_assessment=True,
    )
    assert acts[0]["target"] == "qa"
    assert acts[0]["query"]["child_id"] == "42"
    assert acts[0]["query"]["query"].startswith("我有数学题")


@pytest.mark.asyncio
async def test_trace_on_retrieve_denied_for_wrong_profile():
    result = await call_tool("sandbox.ping", {"token": "x"}, profile="consult")
    assert result.ok is False
    rows = recent()
    assert any(r["tool"] == "sandbox.ping" and r["ok"] is False for r in rows)


@pytest.mark.asyncio
async def test_parent_kb_uses_retrieve_not_guide_kb(db_session):
    from app.services import parent_guide_service

    parent = auth_service.register_child(
        db_session,
        parent_phone="13900007701",
        nickname="家长脱钩",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    child = auth_service.register_child(
        db_session,
        parent_phone="13900007701",
        nickname="孩子脱钩",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    auth_service.bind_parent_child(db_session, parent.id, child.id)
    db_session.commit()

    kb_agent = AsyncMock(return_value={"reply": "不该走 Guide KB"})

    with patch(
        "app.agents.guide.kb_agent.run_guide_kb_turn",
        new=kb_agent,
    ), patch(
        "app.services.doubao_client.is_configured",
        return_value=True,
    ), patch(
        "app.harness.turn.run_profile_turn",
        new=AsyncMock(
            return_value={
                "reply": "家长版：赢者是目标导向。",
                "rag_used": True,
                "tools_used": [{"name": "retrieve_kb", "ok": True}],
            }
        ),
    ):
        out = await parent_guide_service.run_parent_turn(
            db_session, parent.id, "赢者天赋是什么"
        )

    kb_agent.assert_not_called()
    assert out["rag_source"] == "parent_retrieve_kb"
    assert "赢者" in out["reply"]


def test_run_profile_turn_is_fresh_each_call():
    from inspect import signature

    from app.harness.turn import run_profile_turn

    sig = signature(run_profile_turn)
    assert "system_override" in sig.parameters
    assert "history" in sig.parameters


@pytest.mark.asyncio
async def test_qa_tools_registered():
    from app.harness.registry import get_tool

    assert get_tool("retrieve_qa_kb") is not None
    assert get_tool("ocr_extract") is not None
    assert get_tool("vision_ocr") is not None  # ocr_extract 别名
    result = await call_tool("retrieve_qa_kb", {"query": ""}, profile="qa")
    assert result.ok is False
