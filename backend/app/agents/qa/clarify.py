"""QA 弱澄清 — 无题干、无图片时先追问，避免空讲。"""

from __future__ import annotations

import re

from app.agents.qa.router import detect_subject

CLARIFY_REPLY = (
    "同学，还没看到具体题目呢～"
    "请把题干打出来，或者拍一张题拍照发给我，我再一步步帮你讲。"
)

# 仅寒暄/求助、无明显题干（首轮且无图时触发）
# 「不会」族由 clarify_guide 承接，不在此列表
_VAGUE_PHRASES = {
    "帮我",
    "帮帮我",
    "帮我看看",
    "帮我看下",
    "帮我看这道题",
    "请帮我看这道题",
    "看一下",
    "看下",
    "老师",
    "老师好",
    "你好",
    "您好",
    "在吗",
    "请问",
    "求助",
    "怎么做",
    "怎么办",
}

_HAS_STEM_HINT = re.compile(
    r"(\d+\s*[+\-×÷*/=]\s*\d+)|"
    r"(方程|函数|几何|面积|周长|分数|小数|文言文|古诗|作文|时态|语法|单词|"
    r"实验|电路|光合|已知|求|解：|解:|下列|阅读下面|translate|grammar|"
    r"比喻|拟人|修辞|什么是)",
    re.I,
)


def needs_stem_clarification(
    message: str,
    *,
    has_image: bool = False,
    has_prior_turns: bool = False,
) -> bool:
    """首轮、无图、且为寒暄/空求助时，应先澄清。续聊不拦。"""
    if has_image or has_prior_turns:
        return False
    text = (message or "").strip()
    if not text:
        return True
    compact = re.sub(r"\s+", "", text)
    if compact in _VAGUE_PHRASES:
        return True
    if _HAS_STEM_HINT.search(text):
        return False
    _, score = detect_subject(text)
    if score >= 1:
        return False
    # 极短且无任何学科信号
    return len(compact) <= 4


def clarification_reply(subject: str | None = None) -> str:
    subj = (subject or "").strip()
    if subj:
        return (
            f"同学，还没看到「{subj}」的具体题目呢～"
            "请把题干打出来，或者拍一张题拍照发给我，我再一步步帮你讲。"
        )
    return CLARIFY_REPLY
