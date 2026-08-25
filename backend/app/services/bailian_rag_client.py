"""兼容层 — 请优先 `from app.services.bailian import …`。

旧导入路径保留，避免测试/调用方立刻断裂。
"""

from __future__ import annotations

from app.services.bailian import bailian_status, guide_rag_query, rag_query
from app.services.bailian.config import guide_rag_ready as is_bailian_rag_enabled


async def bailian_retrieve(query: str, *, top_n: int = 3, timeout: float = 20):
    """兼容旧 API：返回 dict(rag_block/sources/node_count)。"""
    result = await guide_rag_query(query, timeout=timeout)
    if result is None:
        return None
    # top_n 已在配置侧控制；此处再截断兼容
    if top_n and len(result.nodes) > top_n:
        from dataclasses import replace

        result = replace(result, nodes=result.nodes[:top_n])
    return {
        "rag_block": result.rag_block,
        "sources": result.sources,
        "node_count": result.node_count,
        "mode": result.mode,
    }


__all__ = [
    "bailian_retrieve",
    "bailian_status",
    "is_bailian_rag_enabled",
    "rag_query",
    "guide_rag_query",
]
