"""Agent 间交接协议 — 仅 navigate / handoff，禁止 Agent 互相调用 runner。

Guide → 前端跳转答疑/训练等；不在此 import agents.qa。
"""

from __future__ import annotations

from typing import Any

NAVIGATE_TARGETS = frozenset({
    "talent", "train", "qa", "growth", "report", "history",
})

ACTION_LABELS: dict[str, str] = {
    "talent": "去天赋测试 ›",
    "report": "去天赋报告 ›",
    "train": "去今日训练 ›",
    "qa": "去学科答疑 ›",
    "growth": "去成长里程碑 ›",
    "history": "去历史记录 ›",
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
    ("qa", ("答疑", "作业", "题目", "讲解", "不会做", "功课")),
    (
        "history",
        (
            "历史记录",
            "打卡记录",
            "打卡历史",
            "打卡内容",
            "打卡详情",
            "打卡数值",
            "最近一次",
            "上次打卡",
            "上一次打卡",
            "最近一笔",
        ),
    ),
    (
        "growth",
        (
            "里程碑",
            "徽章",
            "成长记录",
            "还能干",
            "干点什么",
            "接下来做",
        ),
    ),
    (
        "train",
        (
            "今日训练",
            "去训练",
            "开始练",
            "打卡吗",
            "训练如何",
            "今日如何",
            "练得怎样",
            "练得怎么样",
            "完成了吗",
            "打卡情况",
            "做到哪",
            "练了吗",
            "练完了吗",
        ),
    ),
]

_TALENT_TOOL_NAMES = frozenset({"get_talent_report_summary", "get_profile"})


def navigate_action(
    target: str | None,
    *,
    query: dict[str, str] | None = None,
) -> dict | None:
    """白名单校验后的单条 navigate 动作；可选 query（如 history?date=）。"""
    if not target or target not in NAVIGATE_TARGETS:
        return None
    act: dict[str, Any] = {
        "type": "navigate",
        "target": target,
        "label": ACTION_LABELS[target],
    }
    if query:
        clean = {
            str(k): str(v)
            for k, v in query.items()
            if k and v is not None and str(v).strip()
        }
        if clean:
            act["query"] = clean
    return act


def actions_for_next(
    next_action: str | None,
    *,
    query: dict[str, str] | None = None,
) -> list[dict]:
    act = navigate_action(next_action, query=query)
    return [act] if act else []


def _query_date_from_tools(tools_used: list[dict[str, Any]] | None) -> str | None:
    for t in tools_used or []:
        if not isinstance(t, dict):
            continue
        if t.get("name") != "get_day_checkin_detail":
            continue
        qd = str(t.get("query_date") or "").strip()[:10]
        if len(qd) == 10 and qd[4] == "-" and qd[7] == "-":
            return qd
    return None


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
    # 查历史打卡明细：默认导「历史记录」并尽量带上日期；今日语境仍可贴训练
    if "get_day_checkin_detail" in used:
        if any(k in text for k in ("今天", "今日", "开始练", "去训练")) and not any(
            k in text
            for k in ("最近一次", "上次", "上一次", "打卡内容", "打卡详情", "打卡数值", "历史")
        ):
            return "train"
        return "history"
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
    hist_date = _query_date_from_tools(tools_used)
    hist_query = {"date": hist_date} if hist_date else None
    if intent == "talent":
        return actions_for_next("report" if has_assessment else "talent")
    if intent == "history":
        return actions_for_next("history", query=hist_query)
    if intent:
        return actions_for_next(intent)
    return actions_for_next(situation_next)
