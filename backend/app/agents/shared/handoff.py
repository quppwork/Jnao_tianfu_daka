"""Agent 间交接协议 — 仅 navigate / handoff，禁止 Agent 互相调用 runner。

Guide → 前端跳转答疑/训练等；不在此 import agents.qa。

协议要点：
- actions[]：{type: navigate|confirm_write, target|write_op, label, ...}
- next_action：主按钮 target（与 actions 中 navigate 对齐）
- should_route_to_qa：路由层纯函数；真正跳转靠前端执行 actions
- 跨 Agent 不直接 await 对方 runner，只交付 payload / 按钮
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
    ("qa", ("答疑", "作业", "题目", "讲解", "不会做", "功课", "数学题", "语文题", "英语题", "应用题", "计算题")),
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
            "下一等级",
            "下一级",
            "怎么晋级",
            "如何晋级",
            "方案怎么排",
            "怎么排的",
            "训练方案",
            "能练什么",
            "可以训练",
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
    if should_route_to_qa(text):
        return "qa"
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


_SKILL_FOCUS = (
    "超脑阅读",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
)

_QA_SUBJECTS = (
    ("数学", "数学"),
    ("语文", "语文"),
    ("英语", "英语"),
    ("物理", "物理"),
    ("化学", "化学"),
    ("科学", "科学"),
)


def _focus_skill_from_message(message: str) -> str | None:
    text = message or ""
    for sk in _SKILL_FOCUS:
        if sk in text:
            return sk
    return None


_QA_PROBLEM_HINTS = (
    "题",
    "不会做",
    "不会写",
    "不会算",
    "怎么办",
    "怎么解",
    "求解",
    "算一下",
    "作业",
    "功课",
    "讲解",
    "答案",
    "帮我看",
    "帮我解",
    "这道",
    "这题",
)

_QA_PROBLEM_PHRASES = (
    "数学题",
    "语文题",
    "英语题",
    "物理题",
    "化学题",
    "应用题",
    "计算题",
    "我有数学",
    "我有语文",
    "我有英语",
    "我有题",
    "有道题",
    "有个题",
    "不会这题",
    "学科问题",
    "学科题",
)


def should_route_to_qa(message: str) -> bool:
    """学科解题 / 作业类问句 → 学科答疑。"""
    text = (message or "").strip()
    if not text:
        return False
    if any(p in text for p in _QA_PROBLEM_PHRASES):
        return True
    if _qa_subject_from_message(text) and any(h in text for h in _QA_PROBLEM_HINTS):
        return True
    # 「我有…题…怎么办」等口语
    if "题" in text and any(h in text for h in ("怎么办", "怎么做", "不会", "求解", "答案")):
        if not any(k in text for k in ("训练", "打卡", "开口窍", "超脑", "影像", "扫描")):
            return True
    return False


def _intent_from_reply(reply: str) -> str | None:
    """回复正文明确导向某入口时，按钮与之对齐。

    同时提到多个入口时：学科答疑优先于今日训练（避免兜底文案误贴训练按钮）。
    """
    text = (reply or "").strip()
    if not text:
        return None
    if "学科答疑" in text:
        return "qa"
    if "今日训练" in text:
        return "train"
    if "天赋测试" in text or "天赋报告" in text:
        return "talent"
    if "成长里程碑" in text:
        return "growth"
    return None


def primary_navigate_target(actions: list[dict] | None) -> str | None:
    """从 actions 取主跳转 target（忽略 confirm）。"""
    for a in actions or []:
        if isinstance(a, dict) and a.get("type") == "navigate" and a.get("target") in NAVIGATE_TARGETS:
            return str(a["target"])
    return None


def _qa_subject_from_message(message: str) -> str | None:
    text = message or ""
    for key, subj in _QA_SUBJECTS:
        if key in text:
            return subj
    return None


def _handoff_query(
    *,
    intent: str,
    message: str,
    tools_used: list[dict[str, Any]] | None,
) -> dict[str, str] | None:
    """组装跳转 query：date / focus / hint / from=guide。"""
    q: dict[str, str] = {"from": "guide"}
    text = (message or "").strip()
    if text:
        q["hint"] = text[:40]
    if intent == "history":
        qd = _query_date_from_tools(tools_used)
        if qd:
            q["date"] = qd
    if intent == "train":
        focus = _focus_skill_from_message(text)
        if not focus:
            # 从档位工具里取最低档技能作关注提示（非晋级规则）
            for t in tools_used or []:
                brief = t.get("result_brief") if isinstance(t, dict) else None
                if not isinstance(brief, dict) or brief.get("type") != "skill_snapshot":
                    continue
                items = brief.get("items") or []
                if items and isinstance(items[0], dict) and items[0].get("name"):
                    focus = str(items[0]["name"])
                    break
        if focus:
            q["focus"] = focus
    if intent == "qa":
        subj = _qa_subject_from_message(text)
        if subj:
            q["subject"] = subj
    # 仅 from+空 hint 无意义时仍保留 from，便于对端识别来源
    return q


def resolve_reply_actions(
    *,
    situation_next: str | None,
    message: str,
    tools_used: list[dict[str, Any]] | None = None,
    has_assessment: bool = False,
    reply: str | None = None,
) -> list[dict]:
    """优先按本轮意图给按钮；天赋意图且已测评 → 报告页；带深交接 query。"""
    intent = infer_navigate_intent(message, tools_used)
    if not intent and reply:
        intent = _intent_from_reply(reply)
    if intent == "talent":
        target = "report" if has_assessment else "talent"
        return actions_for_next(target, query=_handoff_query(
            intent=target, message=message, tools_used=tools_used,
        ))
    if intent:
        return actions_for_next(
            intent,
            query=_handoff_query(
                intent=intent, message=message, tools_used=tools_used,
            ),
        )
    if situation_next:
        return actions_for_next(
            situation_next,
            query=_handoff_query(
                intent=situation_next,
                message=message,
                tools_used=tools_used,
            ),
        )
    return []
