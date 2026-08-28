"""引导页 — 百炼文档库 Retrieve 问句构建。"""

from __future__ import annotations

# 与训练课表 / handoff 对齐；长名优先匹配
GUIDE_RAG_SKILLS: tuple[str, ...] = (
    "超脑阅读",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
    "精力恢复",
    "高效作业",
    "开口窍",
)

_PRACTICE_PATTERNS: tuple[str, ...] = (
    "怎么练",
    "如何练",
    "怎么练习",
    "如何练习",
    "怎样练",
    "怎样练习",
    "具体怎么",
    "具体如何",
    "怎么训练",
    "如何训练",
)


def is_guide_practice_method_question(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return any(p in text for p in _PRACTICE_PATTERNS)


def extract_guide_skill_focus(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    for skill in sorted(GUIDE_RAG_SKILLS, key=len, reverse=True):
        if skill in text:
            return skill
    return None


def build_guide_rag_query(message: str) -> str:
    """拼 Retrieve 问句：练法类问题优先「技能 + 训练方法 + 练习步骤」。"""
    text = (message or "").strip()
    if not text:
        return ""
    skill = extract_guide_skill_focus(text)
    if is_guide_practice_method_question(text):
        focus = skill or text[:40]
        query = f"{focus} 训练方法 练习步骤 操作方法"
        if skill and skill not in query:
            query = f"{skill} {query}"
        return query[:500]
    if skill:
        return f"{skill} {text}"[:500]
    return text[:500]
