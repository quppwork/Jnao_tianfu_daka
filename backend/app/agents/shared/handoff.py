"""Agent 间交接协议 — 仅 navigate / handoff，禁止 Agent 互相调用 runner。

Guide → 前端跳转答疑/训练等；不在此 import agents.qa。
"""

from __future__ import annotations

from typing import Any

NAVIGATE_TARGETS = frozenset({"talent", "train", "qa", "growth", "report"})

ACTION_LABELS: dict[str, str] = {
    "talent": "去天赋测试 ›",
    "report": "去天赋报告 ›",
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

# 用户问句意图 → navigate target（优先于当日 situation.next_action）
_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "talent",
        ("天赋", "测评", "报告", "什么者", "潜能", "赢者", "学者", "思者", "德者", "行者", "解读"),
    ),
    ("qa", ("答疑", "作业", "题目", "讲解", "不会做")),
    ("growth", ("里程碑", "徽章", "成长记录")),
    ("train", ("今日训练", "去训练", "开始练", "打卡吗")),
]

_TALENT_TOOL_NAMES = frozenset({"get_talent_report_summary", "get_profile"})


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


def infer_navigate_intent(
    message: str,
    tools_used: list[dict[str, Any]] | None = None,
) -> str | None:
    """从用户话或工具调用推断本轮更合适的跳转。"""
    used = {str(t.get("name") or "") for t in (tools_used or [])}
    if "get_talent_report_summary" in used:
        return "talent"
    if used & _TALENT_TOOL_NAMES and any(
        k in (message or "") for k in ("天赋", "测评", "报告", "潜能", "解读", "什么者")
    ):
        return "talent"
    text = (message or "").strip()
    if not text:
        return None
    for target, keys in _INTENT_KEYWORDS:
        if any(k in text for k in keys):
            return target
    return None


def resolve_reply_actions(
    *,
    situation_next: str | None,
    message: str,
    tools_used: list[dict[str, Any]] | None = None,
    has_assessment: bool = False,
) -> list[dict]:
    """优先按本轮意图给按钮；天赋意图且已测评 → 报告页。"""
    intent = infer_navigate_intent(message, tools_used)
    if intent == "talent":
        return actions_for_next("report" if has_assessment else "talent")
    if intent:
        return actions_for_next(intent)
    return actions_for_next(situation_next)
