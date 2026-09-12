"""学科答疑 — 百炼检索问句构建。"""

from __future__ import annotations

from typing import Any

from app.services.kb_policy import active_kb_source_key, kb_single_source

# 与 guide_rag_query / kb_registry tags 对齐
_SKILLS: tuple[str, ...] = (
    "超脑阅读",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
    "开口窍",
    "开口穹",
    "感知力",
    "高效作业",
)

_PRACTICE_HINTS = (
    "怎么练",
    "如何练",
    "怎样练",
    "练法",
    "训练方法",
    "示范",
)


def extract_qa_skill_focus(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    for skill in sorted(_SKILLS, key=len, reverse=True):
        if skill in text:
            return "开口窍" if skill == "开口穹" else skill
    return None


def pick_qa_kb_source_key(message: str) -> str:
    """选源：单库模式下固定 talent_doc（x1micrdmjq）。"""
    if kb_single_source():
        return active_kb_source_key()
    text = (message or "").strip()
    skill = extract_qa_skill_focus(text)
    if skill or any(h in text for h in _PRACTICE_HINTS):
        return "video_practice"
    return "talent_doc"


def build_qa_kb_rounds(
    message: str,
    *,
    subject: str | None = None,
) -> list[dict[str, Any]]:
    """检索计划。单库：仅一轮 talent_doc；双库：主库 + 学科补一轮。"""
    text = (message or "").strip()
    if not text:
        return []

    skill = extract_qa_skill_focus(text)
    primary_key = pick_qa_kb_source_key(text)
    subj = (subject or "").strip()

    if skill:
        primary_query = f"{skill} 训练方法 练习步骤 操作方法"
    elif any(h in text for h in ("怎么学", "如何学", "怎样学", "学习方法", "学法")):
        focus = subj or text[:40]
        primary_query = f"{focus} 学习方法 系统训练 学习规律"
    else:
        primary_query = text[:120]
        if "训练方法" not in primary_query and primary_key == "video_practice":
            primary_query = f"{primary_query} 训练方法"

    rounds: list[dict[str, Any]] = [
        {
            "round": 1,
            "source_key": primary_key,
            "query": primary_query[:500],
        }
    ]

    if kb_single_source():
        # 单库：同库再补一条学科问句，仍指向 x1micrdmjq
        if subj and skill:
            rounds.append(
                {
                    "round": 2,
                    "source_key": primary_key,
                    "query": f"{subj} 系统训练 学习规律 {skill}"[:500],
                }
            )
        elif subj and primary_key == active_kb_source_key():
            rounds.append(
                {
                    "round": 2,
                    "source_key": primary_key,
                    "query": f"{subj} 高效作业 训练方法 学习方法"[:500],
                }
            )
        return rounds

    if subj and primary_key == "talent_doc":
        rounds.append(
            {
                "round": 2,
                "source_key": "video_practice",
                "query": f"{subj} 高效作业 训练方法 注意事项"[:500],
            }
        )
    elif subj and skill:
        rounds.append(
            {
                "round": 2,
                "source_key": "talent_doc",
                "query": f"{subj} 系统训练 学习规律 {skill}"[:500],
            }
        )

    return rounds
