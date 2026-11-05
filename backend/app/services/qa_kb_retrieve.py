"""学科答疑 — 百炼多轮检索（平台特殊训练方法）。"""

from __future__ import annotations

import os
from typing import Any

from app.core.logger import get_logger
from app.services.bailian import rag_query
from app.services.bailian.models import RagResult, merge_rag_results
from app.services.kb_registry import get_kb_registry
from app.services.qa_kb_query import build_qa_kb_rounds

logger = get_logger("qa_kb")


def qa_method_kb_enabled() -> bool:
    return (os.getenv("QA_METHOD_KB") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def qa_method_kb_ready() -> bool:
    if not qa_method_kb_enabled():
        return False
    from app.services.bailian.config import config_ready_for_retrieve, load_bailian_config

    cfg = load_bailian_config()
    if not config_ready_for_retrieve(cfg):
        return False
    return len(get_kb_registry().sources) > 0


async def retrieve_qa_method_kb(
    message: str,
    *,
    subject: str | None = None,
    top_n: int = 4,
    timeout: float = 20,
) -> dict[str, Any] | None:
    """多轮 Retrieve → 合并切片。失败返回 None（runner 降级）。"""
    if not qa_method_kb_ready():
        return None

    rounds = build_qa_kb_rounds(message, subject=subject)
    if not rounds:
        return None

    reg = get_kb_registry()
    results: list[RagResult] = []
    source_keys: list[str] = []
    queries: list[str] = []

    for plan in rounds:
        key = str(plan.get("source_key") or "")
        query = str(plan.get("query") or "").strip()
        src = reg.get(key)
        if not src or not src.index_id or not query:
            continue
        try:
            hit = await rag_query(
                query,
                index_id=src.index_id,
                top_n=max(2, top_n // 2) if len(rounds) > 1 else top_n,
                timeout=timeout,
            )
        except Exception as e:
            logger.warning("qa method kb round failed key=%s: %s", key, e)
            continue
        if not hit or not hit.nodes:
            continue
        results.append(hit)
        if key not in source_keys:
            source_keys.append(key)
        queries.append(query)

    merged = merge_rag_results(*results, mode="retrieve", query=message, top_n=top_n)
    if not merged or not merged.rag_block:
        return None

    return {
        "answer": merged.rag_block,
        "sources": list(merged.sources),
        "source_keys": source_keys,
        "queries": queries,
        "rag_source": "bailian_method",
        "node_count": merged.node_count,
    }
