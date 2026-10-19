"""报告页章节锚点 — 引用（citations）的唯一词表。

两处消费：
- `talent_doc_rag` 工具：按检索命中的 `title` / `doc_name` 归类，随 payload 返回 `citations`
- `report_talent_agent` 门面：老消息 / 工具未带 citations 时按正文关键词兜底

锚点与前端 report-v3.html 的 `.tintro` / `#abilList` / `#hallx` / `#theater` 对齐。
"""

from __future__ import annotations

from typing import Any, Iterable

# 顺序即引用展示优先级
REPORT_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("五维能量星图", ("五维", "星图", "执行力", "公信力", "协调力", "创新力", "领导力")),
    ("名人堂", ("名人堂", "榜样")),
    ("天赋剧场", ("剧场", "短片")),
)

MAX_CITATIONS = 2


def derive_by_keywords(text: str | None, *, exclude: str | None = None) -> list[str]:
    """从回复正文保守推断章节（历史消息 / 工具未给 citations 时的兜底）。"""
    body = (text or "").strip()
    if not body or (exclude and body == exclude):
        return []
    out: list[str] = []
    for label, keys in REPORT_SECTIONS:
        if any(k in body for k in keys):
            out.append(label)
        if len(out) >= MAX_CITATIONS:
            break
    return out


def _label_for(*fields: str) -> str | None:
    blob = "".join(str(f or "") for f in fields)
    if not blob:
        return None
    for label, keys in REPORT_SECTIONS:
        if any(k in blob for k in keys):
            return label
    return None


def sections_from_hits(hits: Iterable[dict[str, Any]] | None) -> list[str]:
    """按 RAG 命中的章节元数据归类，替代对模型正文的关键词猜测。"""
    found: set[str] = set()
    for hit in list(hits or [])[:8]:
        if not isinstance(hit, dict):
            continue
        label = _label_for(hit.get("title") or "", hit.get("doc_name") or "")
        if label:
            found.add(label)
    return [label for label, _ in REPORT_SECTIONS if label in found][:MAX_CITATIONS]
