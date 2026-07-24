# -*- coding: utf-8 -*-
"""首页引导 A2：handoff actions + situation_label"""

from app.agents.shared.handoff import (
    actions_for_next,
    navigate_action,
    situation_label,
)


def test_navigate_whitelist():
    assert navigate_action("train")["type"] == "navigate"
    assert navigate_action("hack") is None
    assert navigate_action(None) is None


def test_actions_for_next():
    acts = actions_for_next("talent")
    assert len(acts) == 1
    assert acts[0]["target"] == "talent"
    assert "天赋" in acts[0]["label"]
    assert actions_for_next("nope") == []


def test_situation_label():
    assert "测评" in situation_label("need_assessment")
    assert situation_label("unknown") == ""
