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
        "你好，我是张宇老师的智能体——大宇智能体，也是你的专属AI教练！"
        "我能根据你的天赋定制课程、带你打卡、帮你解答学习疑惑。"
        "请点击「天赋测试」开始测试喔～做完后记得回来告诉我，我帮你看看结果！"
        "\n\n⚠️ 今天的训练是为「{nickname}」准备的，是你本人吗？"
        "如果不是，请点击顶部「{nickname} ▾」切换账号，避免训练数据混淆哦～"
    ),
    "ready_to_train": (
        "你好，我是张宇老师的智能体——大宇智能体，也是你的专属AI教练！"
        "我能根据你的天赋定制课程、带你打卡、帮你解答学习疑惑。"
        "现在点击「今日训练」选好时长就可以开始打卡啦～"
        "\n\n⚠️ 当前账户是「{nickname}」，是你本人吗？"
        "如果不是，请点击顶部「{nickname} ▾」切换到自己的账户再开始训练～"
    ),
    "training_in_progress": (
        "你好，我是大宇智能体，张宇老师的AI助手。"
        "今天的训练已经开始了，继续完成剩余项目就好。有问题随时问我～"
        "\n\n⚠️ 当前账户是「{nickname}」，确认是本人吗？"
        "不是的话点击顶部「{nickname} ▾」切换账号哦～"
    ),
    "training_done": (
        "今天训练很棒，已经全部完成啦！"
        "有功课问题可以去「学科答疑」，也可以看看「成长里程碑」回顾进步。"
    ),
    "sparse_return": (
        "好久不见！我是大宇智能体，欢迎回来。"
        "有空的话先打开「今日训练」热热身，保持节奏最重要～"
        "\n\n⚠️ 当前登录的是「{nickname}」，是你本人吗？"
        "需要切换账号请点击顶部「{nickname} ▾」。"
    ),
    "assessment_done": (
        "这边检测到你完成天赋测评啦，你真棒～你是一个「{talent}」！"
        "现在点击「今日训练」选好时长就可以开始打卡啦～"
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


def template_welcome(situation: str, *, nickname: str = "", talent: str = "") -> str:
    text = WELCOME_TEMPLATES.get(situation) or WELCOME_TEMPLATES["ready_to_train"]
    name = (nickname or "").strip()
    if name and name not in ("学员", "同学"):
        text = f"{name}，{text}"
    text = text.replace("{nickname}", name or "学员")
    if talent and situation in ("ready_to_train", "training_in_progress", "training_done"):
        text = text.replace(
            "测评已完成，",
            f"这边检测到你完成天赋测评啦，你真棒～你是一个「{talent}」！"
        )
    return text
