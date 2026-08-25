"""引导页 — 是否调用百炼知识库。

与学科答疑 QA RAG 分开：引导页侧重天赋/训练/平台说明；
学科解题类问题不查库（交给学科答疑入口）。
"""

from __future__ import annotations

GUIDE_RAG_PATTERNS = (
    "天赋",
    "学者",
    "思者",
    "赢者",
    "德者",
    "行者",
    "潜能",
    "怎么练",
    "如何练",
    "训练方法",
    "超脑",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "打卡",
    "晋级",
    "平台",
    "四大功能",
    "今日训练",
    "成长里程碑",
    "翻箱",
    "进化",
    "特征",
)

# 明确学科解题 → 不查引导页知识库
HOMEWORK_PATTERNS = (
    "这道题",
    "这题",
    "帮我做",
    "帮我算",
    "求解",
    "答案是",
    "怎么解这",
    "解一下",
    "作业题",
    "应用题",
    "计算题",
)

_GREETINGS = (
    "你好",
    "您好",
    "在吗",
    "嗨",
    "hello",
    "hi",
    "谢谢",
    "感谢",
)


def should_guide_use_rag(
    message: str,
    *,
    use_rag: bool | None = None,
) -> bool:
    if use_rag is False:
        return False
    if use_rag is True:
        return True

    text = (message or "").strip()
    if not text or len(text) < 2:
        return False
    if text.lower() in _GREETINGS or text in _GREETINGS:
        return False
    if any(p in text for p in HOMEWORK_PATTERNS):
        return False
    if any(p in text for p in GUIDE_RAG_PATTERNS):
        return True
    return False
