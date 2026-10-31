"""百炼 RAG 配置 — 对齐官方知识库 API（北京地域）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, *fallbacks: str) -> str:
    v = (os.getenv(name) or "").strip()
    if v:
        return v
    for fb in fallbacks:
        v = (os.getenv(fb) or "").strip()
        if v:
            return v
    return ""


def _truthy(name: str, default: str = "0") -> bool:
    return (os.getenv(name) or default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class BailianConfig:
    """运行时配置快照。"""

    workspace_id: str
    index_id: str
    api_host: str
    endpoint: str
    access_key_id: str
    access_key_secret: str
    dashscope_api_key: str
    agent_id: str
    mode: str  # retrieve | search
    top_n: int
    dense_top_k: int
    enable_reranking: bool
    enable_rewrite: bool
    guide_enabled: bool
    video_index_id: str
    training_rag_enabled: bool
    rag_generate: bool
    generate_model: str
    generate_timeout: float
    rag_fallback_doubao: bool


DEFAULT_OPENAPI_ENDPOINT = "bailian.cn-beijing.aliyuncs.com"


def load_bailian_config() -> BailianConfig:
    ak = _env("ALIBABA_CLOUD_ACCESS_KEY_ID", "OSS_ACCESS_KEY_ID")
    sk = _env("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "OSS_ACCESS_KEY_SECRET")
    workspace = _env("BAILIAN_WORKSPACE_ID", "WORKSPACE_ID")
    api_host = _env("BAILIAN_API_HOST") or (
        f"{workspace}.cn-beijing.maas.aliyuncs.com" if workspace else ""
    )
    mode = (_env("GUIDE_RAG_MODE", "BAILIAN_RAG_MODE") or "retrieve").lower()
    if mode not in ("retrieve", "search"):
        mode = "retrieve"
    top_n = int(_env("BAILIAN_RETRIEVE_TOP_N") or "3")
    dense = int(_env("BAILIAN_DENSE_TOP_K") or str(max(top_n * 2, 6)))
    return BailianConfig(
        workspace_id=workspace,
        index_id=_env("BAILIAN_INDEX_ID"),
        api_host=api_host,
        endpoint=_env("BAILIAN_ENDPOINT") or DEFAULT_OPENAPI_ENDPOINT,
        access_key_id=ak,
        access_key_secret=sk,
        dashscope_api_key=_env("DASHSCOPE_API_KEY"),
        agent_id=_env("BAILIAN_AGENT_ID"),
        mode=mode,
        top_n=max(1, top_n),
        dense_top_k=max(1, dense),
        enable_reranking=_truthy("BAILIAN_ENABLE_RERANKING", "1"),
        enable_rewrite=_truthy("BAILIAN_ENABLE_REWRITE", "0"),
        guide_enabled=_truthy("GUIDE_RAG_ENABLED", "0"),
        video_index_id=_env("BAILIAN_VIDEO_INDEX_ID", "BAILIAN_TRAINING_VIDEO_INDEX_ID"),
        training_rag_enabled=_truthy("TRAINING_RAG_ENABLED", "0"),
        rag_generate=_truthy("BAILIAN_RAG_GENERATE", "0"),
        generate_model=_env("BAILIAN_GENERATE_MODEL") or "qwen3.8-max",
        generate_timeout=float(_env("BAILIAN_GENERATE_TIMEOUT") or "25"),
        rag_fallback_doubao=_truthy("BAILIAN_RAG_FALLBACK_DOUBAO", "1"),
    )


def config_ready_for_retrieve(cfg: BailianConfig | None = None) -> bool:
    c = cfg or load_bailian_config()
    return bool(c.workspace_id and c.index_id and c.access_key_id and c.access_key_secret)


def config_ready_for_search(cfg: BailianConfig | None = None) -> bool:
    c = cfg or load_bailian_config()
    return bool(c.workspace_id and c.api_host and c.agent_id and c.dashscope_api_key)


def guide_rag_ready(cfg: BailianConfig | None = None) -> bool:
    c = cfg or load_bailian_config()
    if not c.guide_enabled:
        return False
    if c.mode == "search":
        return config_ready_for_search(c)
    return config_ready_for_retrieve(c)


def training_rag_ready(cfg: BailianConfig | None = None) -> bool:
    c = cfg or load_bailian_config()
    if not c.training_rag_enabled:
        return False
    if not config_ready_for_retrieve(c):
        return False
    return bool(c.video_index_id)


def config_ready_for_generate(cfg: BailianConfig | None = None) -> bool:
    c = cfg or load_bailian_config()
    return bool(c.workspace_id and c.api_host and c.dashscope_api_key and c.rag_generate)
