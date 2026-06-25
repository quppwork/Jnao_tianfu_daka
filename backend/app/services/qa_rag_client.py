"""代理 D:\\11 enterprise_rag /chat — 学科知识检索"""

from __future__ import annotations

import os

import httpx

from app.core.logger import get_logger
from config.loader import load_settings

logger = get_logger("qa_rag")


def _rag_base_url() -> str:
    settings = load_settings()
    url = settings.get("upstream", {}).get("tianfu_rag", {}).get("url", "")
    return (url or os.getenv("TIANFU_RAG_URL", "http://127.0.0.1:8010")).rstrip("/")


def is_rag_available() -> bool:
    if os.getenv("TIANFU_RAG_MOCK", "") == "1":
        return False
    return bool(_rag_base_url())


async def rag_chat(
    message: str,
    *,
    user_id: str,
    subject: str | None = None,
    timeout: float = 45,
) -> dict | None:
    if not is_rag_available():
        return None
    tags = ["k12_tutor"]
    if subject:
        tags.append(subject)
    payload = {
        "message": message,
        "user_id": user_id,
        "user_department": "k12_tutor",
        "scenario_tags": tags,
        "allowed_sources": ["k12", "jnao_teaching"],
        "max_tokens_answer": 800,
        "hybrid_expert_mode": True,
    }
    api_key = os.getenv("RAG_API_SECRET", "").strip()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{_rag_base_url()}/chat", json=payload, headers=headers)
        if resp.status_code != 200:
            logger.warning(f"RAG chat {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        return {
            "answer": data.get("answer") or "",
            "sources": data.get("sources") or [],
            "source_refs": data.get("source_refs") or [],
        }
    except httpx.HTTPError as e:
        logger.warning(f"RAG request failed: {e}")
        return None
