"""Agent 间交接协议 — 仅 navigate / handoff，禁止 Agent 互相调用 runner。

Guide → 前端跳转答疑/训练等；不在此 import agents.qa。
"""

from __future__ import annotations

NAVIGATE_TARGETS = frozenset({"talent", "train", "qa", "growth"})

ACTION_LABELS: dict[str, str] = {
    "talent": "去天赋测试 ›",
    "train": "去今日训练 ›",
    "qa": "去学科答疑 ›",
    "growth": "去成长里程碑 ›",
}

SITUATION_LABELS: dict[str, str] = {
    "need_assessment": "今日：请先完成天赋测评",
    "ready_to_train": "今日：可以开始训练",
    "training_in_progress": "今日：训练进行中",
    "training_done": "今日：训练已完成",
    "sparse_return": "今日：欢迎回来，建议开练",
}


def navigate_action(target: str | None) -> dict | None:
    """白名单校验后的单条 navigate 动作。"""
    if not target or target not in NAVIGATE_TARGETS:
        return None
    return {
        "type": "navigate",
        "target": target,
        "label": ACTION_LABELS[target],
    }


def actions_for_next(next_action: str | None) -> list[dict]:
    act = navigate_action(next_action)
    return [act] if act else []


def situation_label(situation: str | None) -> str:
    if not situation:
        return ""
    return SITUATION_LABELS.get(situation, "")
