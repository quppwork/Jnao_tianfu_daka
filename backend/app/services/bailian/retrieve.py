"""Retrieve 接口 — OpenAPI + AccessKey。

对应官方：RetrieveRequest（index_id / query / dense / sparse / rerank / rewrite…）
"""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger
from app.services.bailian.client import create_openapi_client
from app.services.bailian.config import BailianConfig, config_ready_for_retrieve, load_bailian_config
from app.services.bailian.models import RagNode, RagResult

logger = get_logger("bailian.retrieve")


def _meta_dict(meta: Any) -> dict[str, Any]:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    # Tea model / nested object
    try:
        return dict(meta)
    except Exception:
        out: dict[str, Any] = {}
        for key in ("doc_name", "doc_id", "title", "content", "_id", "pipeline_id"):
            if hasattr(meta, key):
                out[key] = getattr(meta, key)
        return out


def _node_from_sdk(node: Any) -> RagNode | None:
    meta = _meta_dict(getattr(node, "metadata", None))
    text = (
        getattr(node, "text", None)
        or getattr(node, "content", None)
        or meta.get("content")
        or ""
    )
    text = str(text).strip()
    if not text:
        return None
    score = getattr(node, "score", None)
    try:
        score_f = float(score) if score is not None else None
    except (TypeError, ValueError):
        score_f = None
    return RagNode(
        text=text,
        score=score_f,
        doc_name=str(meta.get("doc_name") or ""),
        doc_id=str(meta.get("doc_id") or ""),
        chunk_id=str(meta.get("_id") or ""),
        title=str(meta.get("title") or ""),
        raw_metadata=meta,
    )


def retrieve_sync(
    query: str,
    *,
    cfg: BailianConfig | None = None,
    index_id: str | None = None,
    top_n: int | None = None,
) -> RagResult | None:
    from alibabacloud_bailian20231229 import models as bailian_models
    from alibabacloud_tea_util import models as util_models

    c = cfg or load_bailian_config()
    if not config_ready_for_retrieve(c):
        logger.warning("bailian retrieve not configured")
        return None

    idx = (index_id or c.index_id).strip()
    n = top_n or c.top_n
    client = create_openapi_client(c)
    request = bailian_models.RetrieveRequest(
        index_id=idx,
        query=query,
        dense_similarity_top_k=c.dense_top_k,
        enable_reranking=c.enable_reranking,
        rerank_top_n=n,
        enable_rewrite=c.enable_rewrite,
    )
    runtime = util_models.RuntimeOptions()
    resp = client.retrieve_with_options(c.workspace_id, request, {}, runtime)
    body = getattr(resp, "body", None)
    data = getattr(body, "data", None) if body else None
    raw_nodes = list(getattr(data, "nodes", None) or []) if data else []

    nodes: list[RagNode] = []
    for raw in raw_nodes:
        parsed = _node_from_sdk(raw)
        if parsed:
            nodes.append(parsed)
        if len(nodes) >= n:
            break

    request_id = getattr(body, "request_id", None) if body else None
    result = RagResult(
        nodes=nodes,
        mode="retrieve",
        query=query,
        request_id=str(request_id) if request_id else None,
    )
    try:
        from app.services.bailian.token_estimate import estimate_retrieve_tokens
        from app.services.usage_recorder import record_usage

        # 官方：Query 向量化 +（可选）初步召回×均长；API 无 usage → 估算
        # prelim 用本次请求的 dense_top_k（控制台默认常为 50，可能更大）
        est = estimate_retrieve_tokens(
            query,
            chunk_texts=[n.text for n in nodes],
            enable_reranking=bool(c.enable_reranking),
            prelim_top_k=int(c.dense_top_k),
            index_count=1,
        )
        record_usage(
            provider="bailian",
            api="retrieve",
            model=idx,
            metric_kind="est_rag",
            call_count=1,
            doc_count=len(nodes),
            # prompt=Query 向量化；completion=Rerank 输入（均为官方「输入 Token」）
            prompt_tokens=est.query_embed_tokens,
            completion_tokens=est.rerank_tokens,
            total_tokens=est.total_tokens,
            estimated=True,
            feature="rag",
            ok=True,
        )
    except Exception as e:
        logger.warning("bailian retrieve usage record skipped: %s", e)
    return result
