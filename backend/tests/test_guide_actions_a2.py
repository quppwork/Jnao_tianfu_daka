# -*- coding: utf-8 -*-
"""首页引导 A2：handoff actions + situation_label"""

from app.agents.shared.handoff import (
    actions_for_next,
    navigate_action,
    resolve_reply_actions,
    situation_label,
)


def test_navigate_whitelist():
    assert navigate_action("train")["type"] == "navigate"
    assert navigate_action("report")["target"] == "report"
    assert navigate_action("hack") is None
    assert navigate_action(None) is None


def test_actions_for_next():
    acts = actions_for_next("talent")
    assert len(acts) == 1
    assert acts[0]["target"] == "talent"
    assert "天赋" in acts[0]["label"]
    assert actions_for_next("nope") == []


def test_resolve_reply_actions_talent_intent():
    """问天赋时不应仍贴「去今日训练」。"""
    acts = resolve_reply_actions(
        situation_next="train",
        message="我这个天赋如何",
        has_assessment=True,
    )
    assert acts and acts[0]["target"] == "report"
    acts2 = resolve_reply_actions(
        situation_next="train",
        message="我这个天赋如何",
        has_assessment=False,
    )
    assert acts2 and acts2[0]["target"] == "talent"


def test_resolve_reply_actions_train_progress_intent():
    """问今日训练进度时应导训练，即使情境默认是 growth。"""
    acts = resolve_reply_actions(
        situation_next="growth",
        message="我今日训练如何",
        has_assessment=True,
    )
    assert acts and acts[0]["target"] == "train"


def test_resolve_reply_actions_what_next_after_done():
    """练完后问还能干嘛 → 成长（或情境 next）。"""
    acts = resolve_reply_actions(
        situation_next="growth",
        message="今天练完了，还能干点什么？",
        has_assessment=True,
    )
    assert acts and acts[0]["target"] == "growth"


def test_situation_label():
    assert "测评" in situation_label("need_assessment")
    assert situation_label("unknown") == ""
