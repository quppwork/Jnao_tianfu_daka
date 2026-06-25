"""学科答疑 — 是否调用 RAG 知识库"""

from __future__ import annotations

from app.services.qa_prompt_builder import RAG_KEYWORDS

TEACHING_PATTERNS = (
    "怎么教",
    "如何教",
    "怎么引导",
    "如何引导",
    "教学法",
    "课标",
    "教案",
    "教学建议",
    "课程标准",
)


def should_use_rag(
    message: str,
    *,
    subject: str | None = None,
    has_image: bool = False,
    use_rag: bool | None = None,
) -> bool:
    if use_rag is False:
        return False
    if use_rag is True:
        return True
    if has_image:
        return False
    text = (message or "").strip()
    if not text:
        return False
    if any(k in text for k in RAG_KEYWORDS):
        return True
    if any(p in text for p in TEACHING_PATTERNS):
        return True
    if subject and ("怎么" in text or "如何" in text) and len(text) > 12:
        return True
    return False
