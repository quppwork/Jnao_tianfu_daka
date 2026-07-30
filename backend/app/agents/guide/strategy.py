"""Guide 个性化策略层（R10）— 按天赋 / 弱项 / 情境注入短策略，避免堆长 prompt。

配置可改文案；红线仍由 persona 统一约束（不讲晋级公式、不编造数字）。
关闭：GUIDE_STRATEGY_ENABLED=0
"""

from __future__ import annotations

import os
from typing import Any

from app.agents.guide.context import GuideContext
from app.agents.guide.long_term import LongTermSummary

# 首页教练口吻（与 QA 解题 hint 区分；可单独改文案）
TALENT_STRATEGY: dict[str, str] = {
    "学者": (
        "天赋侧重「学者」：表达时带一点结构感——先点今日状态，再给下一步；"
        "少空喊口号，帮助对方把今天要做的事看得清楚。"
    ),
    "思者": (
        "天赋侧重「思者」：避免让对方想太远、钻牛角尖；"
        "把下一步收成一件具体可做的小事，提醒先做完再优化。"
    ),
    "行者": (
        "天赋侧重「行者」：多鼓励动手开练、先热身再细想；"
        "少讲大道理，用「先做起来」推动。"
    ),
    "德者": (
        "天赋侧重「德者」：语气温和，多肯定已有的坚持与努力；"
        "避免施压或比较，强调过程本身有价值。"
    ),
    "赢者": (
        "天赋侧重「赢者」：可用轻微「闯关/小目标」感激发动力；"
        "仍保持教练关怀，不制造焦虑催促。"
    ),
}

SITUATION_STRATEGY: dict[str, str] = {
    "need_assessment": (
        "情境「未测评」：优先温和引导完成天赋测评；少展开训练细节与进度数字。"
    ),
    "ready_to_train": (
        "情境「可开练」：给一句可执行的开练建议（有无方案/时长等以工具为准），再自然导向今日训练。"
    ),
    "training_in_progress": (
        "情境「训练进行中」：鼓励续完剩余项；完成情况以工具摘要为准，勿编造。"
    ),
    "training_done": (
        "情境「今日已完成」：先肯定完成，再轻提看详情或成长里程碑；勿反复催再练。"
    ),
    "sparse_return": (
        "情境「掉队召回」：轻松欢迎回来，不指责间隔；强调「练一会儿就好」，不施压。"
    ),
    "assessment_done": (
        "情境「刚完成测评」：简短祝贺天赋方向，并自然衔接到可以开始今日训练。"
    ),
}

_COMMON_FOOTER = (
    "策略仅影响语气与侧重点；事实仍以情境卡片与工具结果为准；"
    "禁止解释 Part/晋级公式/达标次数；禁止编造进度数字。"
)


def strategy_enabled() -> bool:
    return os.getenv("GUIDE_STRATEGY_ENABLED", "1").strip() == "1"


def _normalize_talent(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    for name in TALENT_STRATEGY:
        if s == name or name in s:
            return name
    return None


def resolve_strategy(
    ctx: GuideContext | None,
    long_term: LongTermSummary | None = None,
) -> dict[str, Any]:
    """组装本轮策略；无匹配时返回空 lines。"""
    if not strategy_enabled() or ctx is None:
        return {"enabled": strategy_enabled(), "lines": [], "keys": []}

    lines: list[str] = []
    keys: list[str] = []

    talent_key = _normalize_talent(getattr(ctx, "talent", None))
    if talent_key and talent_key in TALENT_STRATEGY:
        lines.append(TALENT_STRATEGY[talent_key])
        keys.append(f"talent:{talent_key}")

    sit = str(getattr(ctx, "situation", None) or "")
    if sit and sit in SITUATION_STRATEGY:
        lines.append(SITUATION_STRATEGY[sit])
        keys.append(f"situation:{sit}")

    weak: list[str] = []
    if long_term is not None:
        weak = [str(x) for x in (long_term.weak_skills or []) if x][:2]
    if weak:
        focus = "、".join(weak)
        lines.append(
            f"相对弱项（仅语气侧重，勿解释档位/晋级）：{focus}。"
            "可轻提多留意，勿施压、勿承诺天数。"
        )
        keys.append("weak:" + ",".join(weak))

    if lines:
        lines.append(_COMMON_FOOTER)

    return {
        "enabled": True,
        "talent": talent_key,
        "situation": sit or None,
        "weak_skills": weak,
        "keys": keys,
        "lines": lines,
    }


def strategy_to_prompt_block(strategy: dict[str, Any] | None) -> str:
    """空策略返回空串，调用方跳过注入。"""
    if not strategy or not strategy.get("lines"):
        return ""
    body = "\n".join(f"- {ln}" for ln in strategy["lines"])
    return "本轮话术策略（配置，请遵守）：\n" + body
