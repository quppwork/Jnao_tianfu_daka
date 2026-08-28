"""统一 RAG 结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RagNode:
    text: str
    score: float | None = None
    doc_name: str = ""
    doc_id: str = ""
    chunk_id: str = ""
    title: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RagResult:
    """官方 Retrieve/Search 归一化结果 → 注入 LLM 的上下文。"""

    nodes: list[RagNode]
    mode: str
    query: str
    cost_time_ms: int | None = None
    request_id: str | None = None

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def sources(self) -> list[str]:
        out: list[str] = []
        for n in self.nodes:
            name = n.doc_name or n.title
            if name and name not in out:
                out.append(name)
        return out

    @property
    def rag_block(self) -> str:
        if not self.nodes:
            return ""
        parts: list[str] = []
        for i, n in enumerate(self.nodes, 1):
            head = n.doc_name or n.title
            prefix = f"[{i}]" + (f" ({head})" if head else "")
            parts.append(f"{prefix}\n{n.text}".strip())
        return "\n\n".join(parts)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "node_count": self.node_count,
            "sources": self.sources,
            "rag_block": self.rag_block,
            "cost_time_ms": self.cost_time_ms,
            "nodes": [
                {
                    "text": n.text[:200],
                    "score": n.score,
                    "doc_name": n.doc_name,
                    "chunk_id": n.chunk_id,
                }
                for n in self.nodes
            ],
        }


def merge_rag_results(
    *results: RagResult | None,
    mode: str = "retrieve",
    query: str = "",
    top_n: int | None = None,
) -> RagResult | None:
    """合并多库 Retrieve 结果（按 score 去重 doc chunk）。"""
    merged: list[RagNode] = []
    seen: set[str] = set()
    for result in results:
        if not result:
            continue
        for node in result.nodes:
            key = node.chunk_id or f"{node.doc_id}:{node.text[:80]}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(node)
    if not merged:
        return None
    merged.sort(key=lambda n: n.score if n.score is not None else -1.0, reverse=True)
    if top_n is not None and top_n > 0:
        merged = merged[:top_n]
    return RagResult(
        nodes=merged,
        mode=mode,
        query=query or (results[0].query if results and results[0] else ""),
    )
