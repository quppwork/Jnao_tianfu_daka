"""QA「不会」渐进引导（P2/Q10）— 复用顶部学科 chip，不新造题型弹窗。

阶段存在会话 meta；删会话即清空。完整「题型按钮 UI」仍属历史规格，本实现用话术承接。
"""

from __future__ import annotations

import re
from typing import Any

_WONT_PHRASES = {
    "不会",
    "我不会",
    "不会做",
    "不会啊",
    "这题不会",
    "这道题不会",
    "完全不会",
    "不知道",
    "不懂",
    "不明白",
}

_UNCLEAR_PHRASES = {
    "说不清楚",
    "不清楚",
    "不知道怎么说",
    "讲不来",
    "说不清",
    "随便",
    "都行",
}

_STAGE_KEY = "wont_guide_stage"


def _compact(message: str) -> str:
    return re.sub(r"\s+", "", (message or "").strip())


def is_wont_message(message: str) -> bool:
    return _compact(message) in _WONT_PHRASES


def is_unclear_message(message: str) -> bool:
    return _compact(message) in _UNCLEAR_PHRASES


def current_wont_stage(session_meta: dict | None) -> int:
    if not isinstance(session_meta, dict):
        return 0
    try:
        return max(0, int(session_meta.get(_STAGE_KEY) or 0))
    except (TypeError, ValueError):
        return 0


def wont_guide_reply(
    message: str,
    *,
    subject: str | None,
    session_meta: dict | None,
    has_image: bool = False,
) -> tuple[str, dict[str, Any]] | None:
    """若命中「不会」引导，返回 (reply, meta_patch)；否则 None。

    一级：点明当前学科 chip，问哪里不会  
    二级：说不清楚 → 引导拍照/描述  
    （题型 chip UI 不新造，用文字承接二级）
    """
    if has_image:
        return None
    subj = (subject or "当前学科").strip() or "当前学科"
    stage = current_wont_stage(session_meta)
    compact = _compact(message)

    if is_wont_message(message) or (stage >= 1 and is_unclear_message(message)):
        if stage >= 1 or is_unclear_message(message):
            reply = (
                f"没事～你可以拍一张「{subj}」题目照片发给我，"
                "或者试着把题目里看到的字、数字打出来，我一步步帮你看。"
            )
            return reply, {_STAGE_KEY: 2, "clarified": True, "wont_guide": True}
        reply = (
            f"没关系！顶部可以切换学科，当前是「{subj}」。"
            f"好的，{subj}哪里不会？可以说说卡在哪一步；"
            "要是说不清楚，直接拍题或打出题干也行～"
        )
        return reply, {_STAGE_KEY: 1, "clarified": True, "wont_guide": True}

    if stage >= 1 and compact in {"帮我看看", "帮我看下", "看一下", "怎么办", "怎么做"}:
        reply = (
            f"那我们直接看题吧：请拍「{subj}」题目照片，或把题干打出来，"
            "我按步骤帮你拆。"
        )
        return reply, {_STAGE_KEY: 2, "clarified": True, "wont_guide": True}

    return None
