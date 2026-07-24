"""情境判定 + 欢迎模板 — decide / 模板 speak。

situation 枚举与 next_action 白名单见方案文档 §3.2。
"""

from __future__ import annotations

from app.agents.guide.context import GuideContext

# 允许的下一步（前端 navigate 白名单）
NEXT_ACTIONS = frozenset({"talent", "train", "qa", "growth"})

SITUATIONS = frozenset({
    "need_assessment",
    "ready_to_train",
    "training_in_progress",
    "training_done",
    "sparse_return",
})

SPARSE_DAYS_THRESHOLD = 3

# 模板保底（LLM 失败或未配置时使用）
WELCOME_TEMPLATES: dict[str, str] = {
    "need_assessment": (
        "你好！我是张宇老师。建议先完成「天赋测试」，"
        "了解潜能方向后再开始今日训练会更合适。"
    ),
    "ready_to_train": (
        "你好！测评已经就绪。今天可以点开「今日训练」，"
        "选好时长就开始打卡吧。"
    ),
    "training_in_progress": (
        "欢迎回来。今天的训练已经开始了，继续完成剩余项目就好。"
    ),
    "training_done": (
        "今天的训练很棒，已经完成啦。有功课问题可以去「学科答疑」，"
        "也可以看看「成长里程碑」。"
    ),
    "sparse_return": (
        "好久不见！欢迎回来。有空的话先打开「今日训练」热热身，"
        "保持节奏最重要。"
    ),
}


def resolve_situation(ctx: GuideContext) -> tuple[str, str]:
    """根据情境卡片返回 (situation, next_action)。

    优先级：need_assessment > training_done / in_progress > sparse_return > ready_to_train
    """
    if not ctx.has_assessment:
        return "need_assessment", "talent"

    if ctx.today.exists and ctx.today.has_started:
        if ctx.today.status == "completed":
            return "training_done", "qa"
        if ctx.today.item_count > 0 and ctx.today.done_count >= ctx.today.item_count:
            return "training_done", "qa"
        return "training_in_progress", "train"

    days = ctx.days_since_last_checkin
    if days is not None and days >= SPARSE_DAYS_THRESHOLD:
        return "sparse_return", "train"

    return "ready_to_train", "train"


def apply_situation(ctx: GuideContext) -> GuideContext:
    situation, action = resolve_situation(ctx)
    ctx.situation = situation
    ctx.next_action = action
    return ctx


def template_welcome(situation: str, *, nickname: str = "") -> str:
    text = WELCOME_TEMPLATES.get(situation) or WELCOME_TEMPLATES["ready_to_train"]
    name = (nickname or "").strip()
    if name and name not in ("学员", "同学"):
        return f"{name}，{text}"
    return text
