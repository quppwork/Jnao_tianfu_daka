"""完整 RAG 流水线：Query → Retrieve/Search → 归一化切片 → 供 LLM 生成。

对齐官方三种用法中的「API 检索切片 + 自有模型生成」：
- Retrieve：单库 OpenAPI（AccessKey）
- Search：跨库 HTTP（DashScope Key + agent_id）
- 生成：项目内豆包（非百炼应用 rag_options）
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logger import get_logger
from app.services.bailian.config import (
    BailianConfig,
    config_ready_for_retrieve,
    config_ready_for_search,
    guide_rag_ready,
    load_bailian_config,
)
from app.services.bailian.models import RagResult
from app.services.bailian.retrieve import retrieve_sync
from app.services.bailian.search import search_sync

logger = get_logger("bailian.rag")


def _run_sync(
    query: str,
    *,
    cfg: BailianConfig,
    mode: str | None = None,
    index_id: str | None = None,
    top_n: int | None = None,
) -> RagResult | None:
    m = (mode or cfg.mode or "retrieve").lower()
    if m == "search":
        if not config_ready_for_search(cfg):
            # Search 未配齐时回退 Retrieve，避免引导页全挂
            if config_ready_for_retrieve(cfg):
                logger.info("bailian search not ready, fallback to retrieve")
                return retrieve_sync(query, cfg=cfg, index_id=index_id, top_n=top_n)
            return None
        return search_sync(query, cfg=cfg, top_n=top_n)
    if not config_ready_for_retrieve(cfg):
        return None
    return retrieve_sync(query, cfg=cfg, index_id=index_id, top_n=top_n)


async def rag_query(
    query: str,
    *,
    mode: str | None = None,
    index_id: str | None = None,
    top_n: int | None = None,
    timeout: float = 20,
    require_guide_enabled: bool = False,
) -> RagResult | None:
    """异步执行完整检索；失败返回 None（调用方降级为无知识库对话）。"""
    q = (query or "").strip()
    if not q:
        return None
    cfg = load_bailian_config()
    if require_guide_enabled and not guide_rag_ready(cfg):
        return None
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                _run_sync,
                q,
                cfg=cfg,
                mode=mode,
                index_id=index_id,
                top_n=top_n,
            ),
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"bailian rag_query failed: {e}")
        return None


async def guide_rag_query(query: str, *, timeout: float = 20) -> RagResult | None:
    """引导页专用入口：尊重 GUIDE_RAG_ENABLED + 配置就绪。"""
    return await rag_query(query, timeout=timeout, require_guide_enabled=True)


def bailian_status() -> dict[str, Any]:
    cfg = load_bailian_config()
    return {
        "enabled": cfg.guide_enabled,
        "ready": guide_rag_ready(cfg),
        "workspace_id": cfg.workspace_id or None,
        "index_id": cfg.index_id or None,
        "api_host": cfg.api_host or None,
        "endpoint": cfg.endpoint,
        "mode": cfg.mode,
        "top_n": cfg.top_n,
        "dense_top_k": cfg.dense_top_k,
        "enable_reranking": cfg.enable_reranking,
        "enable_rewrite": cfg.enable_rewrite,
        "access_key_ok": bool(cfg.access_key_id),
        "dashscope_key_ok": bool(cfg.dashscope_api_key),
        "agent_id_ok": bool(cfg.agent_id),
        "retrieve_ready": config_ready_for_retrieve(cfg),
        "search_ready": config_ready_for_search(cfg),
        "pipeline": "query → retrieve|search → rerank(optional) → rag_block → doubao",
    }
