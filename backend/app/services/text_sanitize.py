"""用户输入清洗 — 入库前统一处理，降低 XSS / 控制字符风险"""

from __future__ import annotations

import re

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_text(value: str | None, *, max_len: int = 4000) -> str:
    if not value:
        return ""
    text = str(value).strip()
    text = _CONTROL_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    if len(text) > max_len:
        text = text[:max_len]
    return text


def sanitize_subject(value: str | None) -> str | None:
    if not value:
        return None
    allowed = {"数学", "语文", "英语", "科学"}
    text = sanitize_text(value, max_len=20)
    return text if text in allowed else None


def session_title_from_message(message: str) -> str:
    text = sanitize_text(message, max_len=200)
    return text[:30] if text else "新对话"
