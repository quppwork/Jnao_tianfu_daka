# -*- coding: utf-8 -*-
"""首页引导 B：只读工具 + tool-loop 调度"""

import pytest

from app.agents.guide.tools import call_tool, list_tools
from app.agents.guide.tools.planner import (
    _parse_tools_json,
    execute_tools,
    plan_tools_heuristic,
)
from app.agents.guide.runner import run_chat
from app.services.auth_service import register_child


def test_list_tools_includes_builtins():
    names = list_tools()
    assert "get_profile" in names
    assert "get_today_plan" in names
    assert "get_checkin_timeline" in names
    assert "get_skill_progress" in names
    assert "suggest_next_action" in names


def test_plan_tools_heuristic_timeline():
    picks = plan_tools_heuristic("我最近打卡了几次？")
    assert any(p["name"] == "get_checkin_timeline" for p in picks)


def test_plan_tools_heuristic_today():
    picks = plan_tools_heuristic("今天练了吗")
    assert any(p["name"] == "get_today_plan" for p in picks)


def test_plan_tools_heuristic_recommend_and_duration():
    """「练什么 / 练多久」类追问应命中今日摘要，而非空调度。"""
    for msg in (
        "今日你推荐做什么训练项目",
        "可以帮我推荐一下今天训练多久合适吗",
    ):
        picks = plan_tools_heuristic(msg)
        assert any(p["name"] == "get_today_plan" for p in picks), msg


def test_plan_tools_heuristic_empty_for_chitchat():
    assert plan_tools_heuristic("你好呀") == []


def test_parse_tools_json():
    raw = '{"tools":[{"name":"get_profile","args":{}}]}'
    picks = _parse_tools_json(raw)
    assert picks == [{"name": "get_profile", "args": {}}]
    assert _parse_tools_json("不是json") == []
    assert _parse_tools_json('{"tools":[{"name":"hack"}]}') == []


def test_tool_get_profile(db_session):
    user = register_child(db_session, parent_phone="1390000b101", nickname="工具画像")
    out = call_tool(db_session, user.id, "get_profile", {})
    assert out["nickname"] == "工具画像"
    assert "has_assessment" in out


def test_tool_get_today_plan(db_session):
    user = register_child(db_session, parent_phone="1390000b102", nickname="工具今日")
    out = call_tool(db_session, user.id, "get_today_plan", {})
    assert "training_day" in out
    assert "today" in out
    assert out["today"]["exists"] is False


def test_tool_skill_and_suggest(db_session):
    user = register_child(db_session, parent_phone="1390000b103", nickname="工具进度")
    skills = call_tool(db_session, user.id, "get_skill_progress", {})
    assert "overall_tier" in skills
    assert "skills" in skills
    for sd in skills["skills"].values():
        assert "tier" in sd
        assert "consecutive_pass" not in sd
    nxt = call_tool(db_session, user.id, "suggest_next_action", {})
    assert nxt["situation"] == "need_assessment"
    assert nxt["next_action"] == "talent"


def test_tool_checkin_timeline(db_session):
    user = register_child(db_session, parent_phone="1390000b104", nickname="工具时间线")
    out = call_tool(db_session, user.id, "get_checkin_timeline", {"limit": 7})
    assert out["limit"] == 7
    assert out["total_records"] == 0
    assert out["days"] == []


def test_execute_tools_audit(db_session):
    user = register_child(db_session, parent_phone="1390000b105", nickname="工具审计")
    audit, block = execute_tools(
        db_session,
        user.id,
        [{"name": "get_profile", "args": {}}],
    )
    assert audit[0]["ok"] is True
    assert "get_profile" in block


@pytest.mark.asyncio
async def test_run_chat_uses_tools(db_session, mock_doubao):
    user = register_child(db_session, parent_phone="1390000b106", nickname="对话工具")
    result = await run_chat(
        db_session, user.id, "我的天赋测评过了吗", history=[]
    )
    assert result["reply"]
    assert any(t["name"] == "get_profile" for t in result["tools_used"])
