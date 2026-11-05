"""本地脑科学教育知识库检索 — 对应 harness retrieve_kb 的本地回退。

默认路径：环境变量 BRAIN_EDU_KB_PATH，或仓库旁常见 workbuddy 路径。
天赋咨询优先检索 01/02/03。
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# 与 harness LLM 路由层 knowledge.docs 对齐
from app.harness.llm_catalog import FOUNDATION_DOCS

FOUNDATION = FOUNDATION_DOCS

_DEFAULT_CANDIDATES = (
    Path(os.environ.get("BRAIN_EDU_KB_PATH") or ""),
    Path(r"D:\KBdata\first-agent\workbuddy-knowledge\brain-education-kb"),
    Path(__file__).resolve().parents[3] / "workbuddy-knowledge" / "brain-education-kb",
)


def resolve_kb_root() -> Path | None:
    for p in _DEFAULT_CANDIDATES:
        if p and p.is_dir() and any(p.glob("0*.md")):
            return p
    return None


@lru_cache(maxsize=1)
def _load_docs() -> dict[str, str]:
    root = resolve_kb_root()
    if not root:
        return {}
    out: dict[str, str] = {}
    for path in sorted(root.glob("*.md")):
        if path.name.startswith("_") or path.name.upper() == "README.MD":
            continue
        try:
            out[path.name] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def clear_kb_cache() -> None:
    _load_docs.cache_clear()


def _score_chunk(query: str, text: str) -> float:
    q = (query or "").strip().lower()
    if not q or not text:
        return 0.0
    tokens = [t for t in re.split(r"[\s,，。？?！!、；;：:]+", q) if len(t) >= 2]
    if not tokens:
        tokens = [q]
    body = text.lower()
    hit = sum(1 for t in tokens if t in body)
    # 天赋名加权
    for name in ("思者", "赢者", "德者", "行者", "学者", "脑科学", "因材施教"):
        if name in query and name in text:
            hit += 2
    return float(hit) / max(len(tokens), 1)


def _split_sections(doc_name: str, content: str) -> list[tuple[str, str]]:
    """按二级/三级标题切段。"""
    parts: list[tuple[str, str]] = []
    lines = content.splitlines()
    buf: list[str] = []
    title = doc_name
    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if buf:
                parts.append((title, "\n".join(buf).strip()))
            title = line.lstrip("#").strip() or doc_name
            buf = [line]
        else:
            buf.append(line)
    if buf:
        parts.append((title, "\n".join(buf).strip()))
    return parts


def local_retrieve(
    query: str,
    *,
    prefer_docs: list[str] | None = None,
    top_k: int = 4,
    max_chars: int = 2200,
) -> dict[str, Any]:
    """关键词切片检索。返回与 retrieve_kb 相近的结构。"""
    docs = _load_docs()
    if not docs:
        return {
            "ok": True,
            "rag_used": False,
            "rag_block": "",
            "kb_hits": [],
            "sources": [],
            "query": query,
            "mode": "local_missing",
        }

    prefer = prefer_docs or list(FOUNDATION)
    # 优先扫根基三文档，再扫其余
    order = [n for n in prefer if n in docs] + [n for n in docs if n not in prefer]

    scored: list[tuple[float, str, str, str]] = []
    for name in order:
        for title, chunk in _split_sections(name, docs[name]):
            if len(chunk) < 40:
                continue
            s = _score_chunk(query, chunk)
            if name in prefer:
                s *= 1.35
            if s <= 0:
                continue
            scored.append((s, name, title, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = scored[: max(1, top_k)]
    if not picked:
        # 无命中时仍给 02 总览段作弱回退
        fallback = docs.get("02-五者天赋体系.md") or next(iter(docs.values()), "")
        snippet = fallback[:800]
        return {
            "ok": True,
            "rag_used": bool(snippet),
            "rag_block": snippet,
            "kb_hits": [{"score": 0, "text": snippet[:240], "doc": "02-五者天赋体系.md"}],
            "sources": ["02-五者天赋体系.md"] if snippet else [],
            "query": query,
            "mode": "local_weak",
        }

    blocks: list[str] = []
    hits: list[dict[str, Any]] = []
    sources: list[str] = []
    used = 0
    for score, name, title, chunk in picked:
        piece = chunk[:900]
        if used + len(piece) > max_chars:
            piece = piece[: max(0, max_chars - used)]
        if not piece:
            break
        blocks.append(f"【{name} · {title}】\n{piece}")
        hits.append({"score": round(score, 3), "text": piece[:240], "doc": name})
        if name not in sources:
            sources.append(name)
        used += len(piece)

    return {
        "ok": True,
        "rag_used": True,
        "rag_block": "\n\n".join(blocks),
        "kb_hits": hits,
        "sources": sources,
        "query": query,
        "mode": "local_brain_edu",
    }
