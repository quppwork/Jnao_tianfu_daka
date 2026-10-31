"""拍题清晰度 / 多题选择 — 答疑状态机中的「待澄清」态。

在正式讲解前：模糊则请重拍或点题；多题清晰则先问讲哪一题。
启发式为主，不额外打模型；后续可接 LLM 评分。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 题号：第2题 / 2. / （2） / 2、
_QNUM = re.compile(
    r"(?:第\s*[一二三四五六七八九十\d]+\s*题)"
    r"|(?:(?:^|[\n\s])\(?\d{1,2}\)?\s*[.、．)]\s*\S)"
    r"|(?:(?:^|[\n])\d{1,2}\s*[.、．]\s*)",
    re.M,
)
_GARBLED = re.compile(r"[�□�🞎]|\[\?\]|\(\?\)|无法识别|看不清|模糊")
_CJK_OR_ALNUM = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


@dataclass(frozen=True)
class OcrGate:
    """ok | blurry | multi — 非 ok 时应先澄清、不直接开讲。"""

    status: str
    question_count: int
    reason: str
    reply: str


def _count_questions(text: str) -> int:
    hits = _QNUM.findall(text or "")
    return len(hits)


def _garble_ratio(text: str) -> float:
    raw = text or ""
    if not raw.strip():
        return 1.0
    bad = len(_GARBLED.findall(raw))
    # 连续问号/空白过多也算不清
    qmarks = len(re.findall(r"[？?]{2,}", raw))
    useful = len(_CJK_OR_ALNUM.findall(raw))
    if useful < 12:
        return 1.0
    return min(1.0, (bad * 3 + qmarks * 2) / max(useful, 1))


def assess_ocr_gate(ocr_text: str | None, *, user_message: str = "") -> OcrGate | None:
    """评估拍题 OCR 是否需澄清。返回 None 表示可直接讲解。

    状态语义：非 None → awaiting_question_pick（模糊重拍 / 多题点题）。
    """
    # 用户已明确点题（第2题 / 第二题 / 就讲这道）→ 放行，交给模型按会话 OCR 讲
    um = (user_message or "").strip()
    if re.search(r"(第\s*[一二三四五六七八九十\d]+\s*题|就讲|这道)", um):
        return None

    text = (ocr_text or "").strip()
    if not text:
        return OcrGate(
            "blurry",
            0,
            "empty_ocr",
            "同学，这张图我几乎认不出字。"
            "麻烦对准题目再拍一张（尽量平整、光线足），"
            "或者直接打字把题干发我。",
        )

    n = _count_questions(text)
    ratio = _garble_ratio(text)
    useful = len(_CJK_OR_ALNUM.findall(text))

    if useful < 18 or ratio >= 0.08:
        tip = "有几处字迹/公式我看不清"
        if n >= 1:
            tip = f"图上大约有 {n} 道题，其中有的地方有点模糊"
        reply = (
            f"同学，{tip}。"
            "你可以：① 对准模糊那一题再拍一张发我；"
            "② 或者告诉我「讲第几题」，我先按能看清的部分帮你。"
        )
        return OcrGate("blurry", n, "low_signal", reply)

    if n >= 2:
        reply = (
            f"这张图里我认出大约 {n} 道题。"
            "你想先讲哪一题？直接回「第2题」或把那一题的题号发我就行。"
        )
        return OcrGate("multi", n, "multi_question", reply)

    return None
