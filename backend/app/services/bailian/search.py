"""Search 接口 — HTTP + DashScope API Key（官方推荐跨库检索）。

POST https://{workspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/indices/knowledge/search
Authorization: Bearer $DASHSCOPE_API_KEY
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logger import get_logger
from app.services.bailian.config import BailianConfig, config_ready_for_search, load_bailian_config
from app.services.bailian.models import RagNode, RagResult

logger = get_logger("bailian.search")


def _search_url(cfg: BailianConfig) -> str:
    host = cfg.api_host.rstrip("/")
    if host.startswith("http://") or host.startswith("https://"):
        return f"{host}/api/v1/indices/knowledge/search"
    return f"https://{host}/api/v1/indices/knowledge/search"


def search_sync(
    query: str,
    *,
    cfg: BailianConfig | None = None,
    top_n: int | None = None,
    timeout: float = 20,
) -> RagResult | None:
    c = cfg or load_bailian_config()
    if not config_ready_for_search(c):
        logger.warning("bailian search not configured (need agent_id + DASHSCOPE_API_KEY)")
        return None

    n = top_n or c.top_n
    url = _search_url(c)
    headers = {
        "Authorization": f"Bearer {c.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "agent_id": c.agent_id,
        "query": query,
        "images": [],
    }
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        resp = client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        logger.warning(f"bailian search HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()
    body = data.get("data") or {}
    raw_nodes = body.get("nodes") or []
    nodes: list[RagNode] = []
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        meta = raw.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        text = (raw.get("text") or meta.get("content") or "").strip()
        if not text:
            continue
        score = raw.get("score")
        try:
            score_f = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_f = None
        nodes.append(
            RagNode(
                text=text,
                score=score_f,
                doc_name=str(meta.get("doc_name") or ""),
                doc_id=str(meta.get("doc_id") or ""),
                chunk_id=str(meta.get("_id") or ""),
                title=str(meta.get("title") or ""),
                raw_metadata=meta,
            )
        )
        if len(nodes) >= n:
            break

    cost = body.get("cost_time")
    try:
        cost_ms = int(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost_ms = None

    return RagResult(
        nodes=nodes,
        mode="search",
        query=query,
        cost_time_ms=cost_ms,
        request_id=str(data.get("request_id") or "") or None,
    )


def list_indices_sync(cfg: BailianConfig | None = None) -> list[dict[str, Any]]:
    """管理：列出业务空间下知识库（OpenAPI ListIndices）。"""
    from alibabacloud_bailian20231229 import models as bailian_models
    from alibabacloud_tea_util import models as util_models

    from app.services.bailian.client import create_openapi_client

    c = cfg or load_bailian_config()
    if not (c.access_key_id and c.access_key_secret and c.workspace_id):
        return []

    client = create_openapi_client(c)
    request = bailian_models.ListIndicesRequest()
    runtime = util_models.RuntimeOptions()
    resp = client.list_indices_with_options(c.workspace_id, request, {}, runtime)
    data = getattr(getattr(resp, "body", None), "data", None)
    indices = list(getattr(data, "indices", None) or getattr(data, "IndexList", None) or [])
    # SDK 字段名可能随版本变化，尽量兼容
    if not indices and data is not None:
        for attr in ("indices", "index_list", "list"):
            v = getattr(data, attr, None)
            if v:
                indices = list(v)
                break

    out: list[dict[str, Any]] = []
    for item in indices:
        if isinstance(item, dict):
            out.append(item)
            continue
        out.append(
            {
                "id": getattr(item, "id", None) or getattr(item, "IndexId", None),
                "name": getattr(item, "name", None) or getattr(item, "Name", None),
                "status": getattr(item, "status", None),
            }
        )
    return out
