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
    config_ready_for_generate,
    config_ready_for_retrieve,
    config_ready_for_search,
    guide_rag_ready,
    load_bailian_config,
    training_rag_ready,
)
from app.services.bailian.generate import generate_stream_sync, generate_sync
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


async def training_rag_query(query: str, *, timeout: float = 20) -> RagResult | None:
    """训练页专用：查音视频/训练视频知识库（BAILIAN_VIDEO_INDEX_ID）。"""
    q = (query or "").strip()
    if not q:
        return None
    cfg = load_bailian_config()
    if not training_rag_ready(cfg):
        return None
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                _run_sync,
                q,
                cfg=cfg,
                index_id=cfg.video_index_id,
            ),
            timeout=timeout,
        )
    except Exception as e:
        logger.warning(f"bailian training_rag_query failed: {e}")
        return None


async def guide_knowledge_reply(
    query: str,
    *,
    instructions: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """引导页：百炼直答（文档库），不经过豆包。"""
    cfg = load_bailian_config()
    if not (guide_rag_ready(cfg) and config_ready_for_generate(cfg) and cfg.index_id):
        return None
    q = (query or "").strip()
    if not q:
        return None
    t = timeout if timeout is not None else cfg.generate_timeout
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                generate_sync,
                q,
                index_id=cfg.index_id,
                cfg=cfg,
                instructions=instructions,
                timeout=t,
            ),
            timeout=t + 2,
        )
    except asyncio.TimeoutError:
        logger.warning("bailian guide_knowledge_reply timeout query=%r", q[:80])
        return None
    except Exception as e:
        logger.warning(f"bailian guide_knowledge_reply failed: {e}")
        return None


async def training_knowledge_reply(
    query: str,
    *,
    instructions: str | None = None,
    timeout: float | None = None,
) -> str | None:
    """训练页：百炼直答（视频库），不经过豆包。"""
    cfg = load_bailian_config()
    if not (training_rag_ready(cfg) and config_ready_for_generate(cfg)):
        return None
    q = (query or "").strip()
    if not q:
        return None
    t = timeout if timeout is not None else cfg.generate_timeout
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                generate_sync,
                q,
                index_id=cfg.video_index_id,
                cfg=cfg,
                instructions=instructions,
                timeout=t,
            ),
            timeout=t + 2,
        )
    except asyncio.TimeoutError:
        logger.warning("bailian training_knowledge_reply timeout query=%r", q[:80])
        return None
    except Exception as e:
        logger.warning(f"bailian training_knowledge_reply failed: {e}")
        return None


def guide_knowledge_reply_stream(
    query: str,
    *,
    instructions: str | None = None,
):
    cfg = load_bailian_config()
    if not (guide_rag_ready(cfg) and config_ready_for_generate(cfg) and cfg.index_id):
        return
    q = (query or "").strip()
    if not q:
        return
    yield from generate_stream_sync(
        q,
        index_id=cfg.index_id,
        cfg=cfg,
        instructions=instructions,
    )


def bailian_status() -> dict[str, Any]:
    cfg = load_bailian_config()
    return {
        "enabled": cfg.guide_enabled,
        "ready": guide_rag_ready(cfg),
        "workspace_id": cfg.workspace_id or None,
        "index_id": cfg.index_id or None,
        "video_index_id": cfg.video_index_id or None,
        "training_rag_enabled": cfg.training_rag_enabled,
        "training_rag_ready": training_rag_ready(cfg),
        "rag_generate": cfg.rag_generate,
        "generate_ready": config_ready_for_generate(cfg),
        "generate_model": cfg.generate_model,
        "generate_timeout": cfg.generate_timeout,
        "rag_fallback_doubao": cfg.rag_fallback_doubao,
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
        "pipeline": "query → Retrieve 切片 → 豆包生成 | file_search 直答（可选）",
    }
