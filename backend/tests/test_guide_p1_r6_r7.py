# -*- coding: utf-8 -*-
"""P1 R6/R7：ui blocks + 深交接 query。"""

from app.agents.guide.ui_blocks import build_ui_blocks, result_brief_for_tool
from app.agents.shared.handoff import resolve_reply_actions


def test_result_brief_today_plan():
    brief = result_brief_for_tool(
        "get_today_plan",
        {
            "today": {
                "exists": True,
                "planned_minutes": 30,
                "item_count": 4,
                "done_count": 1,
                "status": "in_progress",
            }
        },
    )
    assert brief and brief["type"] == "today_summary"
    assert any(i["label"] == "计划时长" for i in brief["items"])


def test_result_brief_skill_snapshot():
    brief = result_brief_for_tool(
        "get_skill_progress",
        {
            "overall_tier": 2,
            "skills": {"超脑阅读": {"tier": 1}, "影像追忆": {"tier": 3}},
        },
    )
    assert brief and brief["type"] == "skill_snapshot"
    assert brief["items"][0]["name"] == "超脑阅读"
    assert brief["items"][0]["tier"] == 1


def test_build_ui_blocks_dedupe():
    tools = [
        {
            "name": "get_today_plan",
            "ok": True,
            "result_brief": {
                "type": "today_summary",
                "title": "今日训练",
                "items": [],
            },
        },
        {
            "name": "get_today_plan",
            "ok": True,
            "result_brief": {
                "type": "today_summary",
                "title": "重复",
                "items": [],
            },
        },
        {
            "name": "get_skill_progress",
            "ok": True,
            "result_brief": {
                "type": "skill_snapshot",
                "title": "技能",
                "items": [],
            },
        },
    ]
    blocks = build_ui_blocks(tools)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "today_summary"
    assert blocks[1]["type"] == "skill_snapshot"


def test_handoff_history_keeps_date_and_from():
    acts = resolve_reply_actions(
        situation_next="train",
        message="给出最近一次的打卡内容",
        tools_used=[{
            "name": "get_day_checkin_detail",
            "ok": True,
            "query_date": "2026-07-25",
        }],
        has_assessment=True,
    )
    q = acts[0].get("query") or {}
    assert acts[0]["target"] == "history"
    assert q.get("date") == "2026-07-25"
    assert q.get("from") == "guide"
    assert q.get("hint")


def test_handoff_train_focus_from_message():
    acts = resolve_reply_actions(
        situation_next="train",
        message="帮我关注超脑阅读",
        has_assessment=True,
    )
    assert acts and acts[0]["target"] == "train"
    q = acts[0].get("query") or {}
    assert q.get("from") == "guide"
    assert q.get("focus") == "超脑阅读"


def test_handoff_train_focus_from_skill_snapshot():
    acts = resolve_reply_actions(
        situation_next="train",
        message="我今日训练如何",
        tools_used=[{
            "name": "get_skill_progress",
            "ok": True,
            "result_brief": {
                "type": "skill_snapshot",
                "items": [
                    {"name": "扫描速记", "tier": 1},
                    {"name": "超脑阅读", "tier": 2},
                ],
            },
        }],
        has_assessment=True,
    )
    assert acts[0]["target"] == "train"
    assert acts[0].get("query", {}).get("focus") == "扫描速记"
