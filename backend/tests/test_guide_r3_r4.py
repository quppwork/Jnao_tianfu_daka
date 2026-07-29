# -*- coding: utf-8 -*-
"""R3/R4：查询归一、二次规划、grounding 提示"""

import pytest

from app.agents.guide.tools.planner import (
    build_grounding_hint,
    plan_tools_heuristic,
)
from app.agents.guide.tools.query_normalize import (
    looks_like_business_query,
    looks_like_needs_clarify,
    normalize_guide_query,
)


def test_normalize_typo_and_synonym():
    out = normalize_guide_query("给我看看打卡内同")
    assert "打卡内容" in out


def test_normalize_cooccurrence_unordered():
    """语序颠倒：内容…打卡 → 补上「打卡内容」"""
    out = normalize_guide_query("具体的内容打卡是什么")
    assert "打卡内容" in out


def test_normalize_numeric_synonym():
    out = normalize_guide_query("具体的打卡数值呢")
    assert "打卡内容" in out


def test_heuristic_hits_after_normalize_typo():
    norm = normalize_guide_query("打卡内同写了啥")
    picks = plan_tools_heuristic(norm)
    assert any(p["name"] == "get_day_checkin_detail" for p in picks)


def test_heuristic_hits_cooccurrence():
    norm = normalize_guide_query("内容打卡给我看看")
    picks = plan_tools_heuristic(norm)
    assert any(p["name"] == "get_day_checkin_detail" for p in picks)


def test_looks_like_business_and_clarify():
    assert looks_like_business_query("最近一次打卡怎么样")
    assert not looks_like_business_query("你好呀")
    assert looks_like_needs_clarify("那天练得怎么样")
    assert not looks_like_needs_clarify("2026-07-25 练得怎么样")


def test_grounding_hint_no_tools_business():
    hint = build_grounding_hint("今日训练如何", tools_used=[], tool_block="")
    assert "调度" in hint or "澄清" in hint or "禁止编造" in hint


def test_grounding_hint_with_tools():
    hint = build_grounding_hint(
        "最近一次打卡",
        tools_used=[{
            "name": "get_day_checkin_detail",
            "ok": True,
            "record_count": 1,
        }],
        tool_block="[get_day_checkin_detail] {}",
    )
    assert "Grounding" in hint


def test_grounding_hint_empty_checkin():
    hint = build_grounding_hint(
        "今天打卡内容",
        tools_used=[{
            "name": "get_day_checkin_detail",
            "ok": True,
            "record_count": 0,
            "mode": "today",
        }],
        tool_block="[get_day_checkin_detail] {}",
    )
    assert "为空" in hint or "澄清" in hint


@pytest.mark.asyncio
async def test_plan_tools_uses_normalize_when_fc_empty(monkeypatch):
    """FC 空时，归一后的启发式应能命中错字问句。"""
    from app.agents.guide.tools import planner as pl

    async def empty_fc(message, **kwargs):
        return []

    monkeypatch.setattr(pl, "plan_tools_native_fc", empty_fc)
    monkeypatch.setattr(pl, "plan_tools_llm", empty_fc)
    picks = await pl.plan_tools(
        "打卡内同是什么",
        prefer_native_fc=True,
        use_llm_fallback=True,
    )
    assert any(p["name"] == "get_day_checkin_detail" for p in picks)
