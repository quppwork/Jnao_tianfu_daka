# -*- coding: utf-8 -*-
"""首页引导 B：只读工具 + tool-loop 调度"""

import pytest

from app.agents.guide.tools import call_tool, list_tools
from app.agents.guide.tools.planner import (
    _parse_tools_json,
    execute_tools,
    openai_tool_schemas,
    parse_native_tool_calls,
    plan_tools,
    plan_tools_heuristic,
)
from app.agents.guide.runner import run_chat
from app.services.auth_service import register_child


def test_list_tools_includes_builtins():
    names = list_tools()
    assert "get_profile" in names
    assert "get_talent_report_summary" in names
    assert "get_today_plan" in names
    assert "get_checkin_timeline" in names
    assert "get_skill_progress" in names
    assert "suggest_next_action" in names


def test_openai_tool_schemas_cover_catalog():
    schemas = openai_tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == set(list_tools())
    checkin = next(s for s in schemas if s["function"]["name"] == "get_checkin_timeline")
    assert "limit" in checkin["function"]["parameters"]["properties"]


def test_parse_native_tool_calls():
    msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_today_plan",
                    "arguments": "{}",
                },
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {
                    "name": "get_checkin_timeline",
                    "arguments": '{"limit": 7}',
                },
            },
            {
                "id": "call_hack",
                "type": "function",
                "function": {"name": "hack", "arguments": "{}"},
            },
        ],
    }
    picks = parse_native_tool_calls(msg)
    assert picks == [
        {"name": "get_today_plan", "args": {}},
        {"name": "get_checkin_timeline", "args": {"limit": 7}},
    ]
    assert parse_native_tool_calls(None) == []
    assert parse_native_tool_calls({"role": "assistant", "content": "hi"}) == []


@pytest.mark.asyncio
async def test_plan_tools_prefers_native_fc(mock_doubao):
    mock_doubao["fc"].return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "get_profile",
                    "arguments": "{}",
                },
            }
        ],
    }
    # 无关键词命中启发式；应走 FC
    picks = await plan_tools("帮我看看学生基本信息", prefer_native_fc=True)
    assert picks == [{"name": "get_profile", "args": {}}]
    mock_doubao["fc"].assert_awaited()
    call_kw = mock_doubao["fc"].await_args.kwargs
    assert call_kw.get("tools")
    assert call_kw.get("tool_choice") == "auto"


@pytest.mark.asyncio
async def test_plan_tools_fc_empty_falls_to_heuristic(mock_doubao):
    mock_doubao["fc"].return_value = {"role": "assistant", "content": ""}
    picks = await plan_tools("今天练了吗", prefer_native_fc=True)
    assert any(p["name"] == "get_today_plan" for p in picks)


def test_plan_tools_heuristic_talent_report():
    picks = plan_tools_heuristic("我这个天赋如何")
    assert any(p["name"] == "get_talent_report_summary" for p in picks)


def test_enrich_picks_cross_topic_after_training():
    """先问训练再问天赋 → 补今日摘要，便于关联回答。"""
    from app.agents.guide.tools.planner import enrich_picks_cross_topic

    hist = [
        {"role": "user", "content": "今日训练如何"},
        {
            "role": "assistant",
            "content": "今天的20分钟训练已经完成啦，1项任务都打卡成功～",
        },
    ]
    base = plan_tools_heuristic("我这个天赋如何")
    picks = enrich_picks_cross_topic("我这个天赋如何", base, history=hist)
    names = {p["name"] for p in picks}
    assert "get_talent_report_summary" in names
    assert "get_today_plan" in names


def test_enrich_picks_cross_topic_after_talent():
    """先问天赋再问训练 → 补天赋摘要。"""
    from app.agents.guide.tools.planner import enrich_picks_cross_topic

    hist = [
        {"role": "user", "content": "我这个天赋如何"},
        {"role": "assistant", "content": "你是天生的赢者，完整报告可以去天赋报告页看。"},
    ]
    base = plan_tools_heuristic("今日训练如何")
    picks = enrich_picks_cross_topic("今日训练如何", base, history=hist)
    names = {p["name"] for p in picks}
    assert "get_today_plan" in names
    assert "get_talent_report_summary" in names


def test_clamp_disallowed_tool_pair():
    from app.agents.guide.tools.planner import clamp_to_allowed_pairs

    picks = [
        {"name": "get_checkin_timeline", "args": {"limit": 14}},
        {"name": "get_talent_report_summary", "args": {}},
    ]
    clamped = clamp_to_allowed_pairs(picks)
    assert clamped == [{"name": "get_checkin_timeline", "args": {"limit": 14}}]


def test_enrich_ignores_old_history_beyond_cross_window():
    """超过 CROSS_HISTORY_TURNS 的旧训练话题不应再触发交叉补工具。"""
    from app.agents.guide.tools.planner import (
        CROSS_HISTORY_TURNS,
        enrich_picks_cross_topic,
    )

    hist = [
        {"role": "user", "content": "今日训练如何"},
        {"role": "assistant", "content": "训练已完成。"},
    ]
    # 中间塞满无关轮次，把训练推到窗口外
    for i in range(CROSS_HISTORY_TURNS):
        hist.append({"role": "user", "content": f"闲聊{i}"})
        hist.append({"role": "assistant", "content": f"嗯{i}"})
    base = plan_tools_heuristic("我这个天赋如何")
    picks = enrich_picks_cross_topic("我这个天赋如何", base, history=hist)
    names = {p["name"] for p in picks}
    assert "get_talent_report_summary" in names
    assert "get_today_plan" not in names


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


def test_tool_talent_report_summary(db_session):
    from app.services.assessment_service import save_assessment

    user = register_child(db_session, parent_phone="1390000b110", nickname="工具报告")
    empty = call_tool(db_session, user.id, "get_talent_report_summary", {})
    assert empty.get("has_assessment") is False

    save_assessment(
        db_session,
        child_user_id=user.id,
        jnao_record_id=f"tool-talent-{user.id}",
        answer_bitstring="1" * 35,
        test_type=1,
        report={
            "talent": "赢者",
            "check_talent": ["赢者", "行者"],
            "results": {
                "Talent": {
                    "desp": "<p><strong>【天赋能力解读】</strong></p><p>赢者擅长目标与节奏。</p>"
                    "<p><strong>想对你说的话</strong></p><p>保持闯关感。</p>"
                    "<p><strong>三条黄金建议</strong></p><p>1. 设小目标 2. 及时反馈 3. 适度竞赛</p>"
                },
                "State": {"name": "相生", "desp": "<p>状态良好，适合推进训练。</p>"},
            },
            "create_time": "2026-06-18",
        },
    )
    out = call_tool(db_session, user.id, "get_talent_report_summary", {})
    assert out["has_assessment"] is True
    assert out["talent_primary"] == "赢者"
    assert "赢者" in (out.get("ability_desc") or out.get("coach_hint") or "")


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
    used = {t["name"] for t in result["tools_used"]}
    assert used & {"get_profile", "get_talent_report_summary"}
    assert result["actions"] and result["actions"][0]["target"] in ("talent", "report")
