# -*- coding: utf-8 -*-
"""QA P2：短策略层 + 「不会」渐进引导。"""

from app.agents.qa.clarify_guide import wont_guide_reply
from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.agents.qa.strategy import (
    resolve_qa_strategy,
    strategy_to_prompt_block,
)


def test_qa_strategy_talent_and_stage():
    s = resolve_qa_strategy(talent_primary="学者", school_stage="junior", has_image=False)
    assert "talent:学者" in s["keys"]
    assert "stage:junior" in s["keys"]
    block = strategy_to_prompt_block(s)
    assert "学者" in block
    assert "初中" in block or "junior" in block or "推理" in block
    prompt = build_qa_system_prompt(subject="数学", strategy_block=block)
    assert "辅导策略" in prompt


def test_qa_strategy_image_key():
    s = resolve_qa_strategy(talent_primary="行者", school_stage="primary_low", has_image=True)
    assert "modality:image" in s["keys"]
    assert "图" in strategy_to_prompt_block(s)


def test_qa_strategy_disabled(monkeypatch):
    monkeypatch.setenv("QA_STRATEGY_ENABLED", "0")
    s = resolve_qa_strategy(talent_primary="赢者", school_stage="senior")
    assert s["lines"] == []
    assert strategy_to_prompt_block(s) == ""


def test_wont_guide_level1():
    got = wont_guide_reply("不会", subject="数学", session_meta=None)
    assert got is not None
    reply, patch = got
    assert "数学" in reply
    assert patch.get("wont_guide_stage") == 1


def test_wont_guide_level2_unclear():
    got = wont_guide_reply(
        "说不清楚",
        subject="语文",
        session_meta={"wont_guide_stage": 1},
    )
    assert got is not None
    reply, patch = got
    assert "拍" in reply or "题干" in reply
    assert patch.get("wont_guide_stage") == 2


def test_wont_guide_skips_with_image():
    assert wont_guide_reply("不会", subject="数学", session_meta=None, has_image=True) is None


def test_wont_guide_api(client, child_with_assessment, mock_doubao):
    uid = child_with_assessment
    r1 = client.post(
        f"/api/qa/chat?user_id={uid}",
        json={"message": "不会", "subject": "数学"},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1.get("clarified") is True
    assert d1.get("wont_guide") is True
    assert "数学" in d1["reply"]
    assert mock_doubao["chat"].call_count == 0

    r2 = client.post(
        f"/api/qa/chat?user_id={uid}",
        json={"message": "说不清楚", "subject": "数学", "session_id": d1["session_id"]},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2.get("wont_guide") is True
    assert "拍" in d2["reply"] or "题干" in d2["reply"]
    assert mock_doubao["chat"].call_count == 0
