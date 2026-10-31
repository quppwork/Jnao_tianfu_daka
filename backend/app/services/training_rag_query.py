"""训练页 — 百炼视频库检索 query 构建。"""

from __future__ import annotations


def build_training_rag_query(
    *,
    talent_primary: str | None = None,
    lesson_title: str | None = None,
    item_titles: list[str] | None = None,
    yesterday_summary: str | None = None,
) -> str:
    """根据今日排课与天赋拼检索问句，供音视频知识库 Retrieve。"""
    parts: list[str] = []
    talent = (talent_primary or "").strip()
    if talent:
        parts.append(f"{talent}天赋训练")
    lesson = (lesson_title or "").strip()
    if lesson:
        parts.append(lesson)
    for title in item_titles or []:
        t = (title or "").strip()
        if t and t not in parts:
            parts.append(t)
    summary = (yesterday_summary or "").strip()
    if summary:
        parts.append(summary)
    query = " ".join(parts).strip()
    return query[:500] if query else "今日训练方法与注意事项"
