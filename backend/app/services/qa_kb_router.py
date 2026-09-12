"""学科答疑 — 是否 / 走哪条知识库路径。

METHOD：百炼练法/天赋库（平台特殊训练方法）
LEGACY_TEACHING：旧 tianfu_rag 教学法
NONE：纯解题 / 闲聊 / 拍图，不查库
"""

from __future__ import annotations

from enum import Enum


class QaKbPath(str, Enum):
    NONE = "none"
    METHOD = "method"
    LEGACY_TEACHING = "legacy_teaching"


# 学法 / 平台练法 → 百炼 METHOD
METHOD_PATTERNS = (
    "怎么学",
    "如何学",
    "怎样学",
    "学习方法",
    "学法",
    "怎么练",
    "如何练",
    "怎样练",
    "训练方法",
    "练法",
    "系统训练",
    "高效作业",
    "开口窍",
    "开口穹",
    "超脑阅读",
    "超脑",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
    "感知力",
)

# 教学法 / 课标 → 旧 RAG
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

# 明确解题 → 不查 METHOD（也不走旧库，除非教学关键词）
HOMEWORK_PATTERNS = (
    "这道题",
    "这题",
    "帮我做",
    "帮我算",
    "帮我看这道",
    "求解",
    "答案是",
    "怎么解这",
    "解一下",
    "作业题",
    "应用题",
    "计算题",
    "怎么解",
    "如何解",
)


def _has_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(p in text for p in patterns)


def resolve_qa_kb_path(
    message: str,
    *,
    subject: str | None = None,
    has_image: bool = False,
    use_rag: bool | None = None,
) -> QaKbPath:
    if use_rag is False:
        return QaKbPath.NONE

    text = (message or "").strip()
    if not text:
        return QaKbPath.NONE

    teaching = _has_any(text, TEACHING_PATTERNS)
    method = _has_any(text, METHOD_PATTERNS)
    homework = _has_any(text, HOMEWORK_PATTERNS)

    if use_rag is True:
        if teaching and not method:
            return QaKbPath.LEGACY_TEACHING
        return QaKbPath.METHOD

    if has_image:
        return QaKbPath.NONE

    # 教学优先于学法（「怎么引导」类）
    if teaching:
        return QaKbPath.LEGACY_TEACHING

    if method:
        return QaKbPath.METHOD

    # 纯解题不查库
    if homework:
        return QaKbPath.NONE

    # 兼容旧规则：指定学科 + 怎么/如何 + 较长问句 → 旧教学法库
    if subject and ("怎么" in text or "如何" in text) and len(text) > 12:
        return QaKbPath.LEGACY_TEACHING

    return QaKbPath.NONE
