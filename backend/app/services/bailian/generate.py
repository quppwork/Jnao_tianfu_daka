"""百炼知识库直答 — Responses API + file_search（检索+生成一次完成）。

对齐官方：https://help.aliyun.com/zh/model-studio/file-search
返回模型生成的 output_text，不再经项目内豆包二次加工。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.logger import get_logger
from app.services.bailian.config import BailianConfig, config_ready_for_generate, load_bailian_config

logger = get_logger("bailian.generate")

DEFAULT_GENERATE_MODEL = "qwen3.8-max"


def _responses_url(cfg: BailianConfig) -> str:
    host = cfg.api_host.rstrip("/")
    if host.startswith("http://") or host.startswith("https://"):
        base = host
    else:
        base = f"https://{host}"
    return f"{base}/compatible-mode/v1/responses"


def _extract_output_text(data: dict[str, Any]) -> str:
    direct = (data.get("output_text") or "").strip()
    if direct:
        return direct
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for block in item.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "output_text":
                    text = (block.get("text") or "").strip()
                    if text:
                        parts.append(text)
    return "\n".join(parts).strip()


def generate_sync(
    query: str,
    *,
    index_id: str,
    cfg: BailianConfig | None = None,
    instructions: str | None = None,
    timeout: float = 45,
) -> str | None:
    c = cfg or load_bailian_config()
    if not config_ready_for_generate(c):
        logger.warning("bailian generate not configured")
        return None
    idx = (index_id or "").strip()
    q = (query or "").strip()
    if not idx or not q:
        return None

    payload: dict[str, Any] = {
        "model": c.generate_model or DEFAULT_GENERATE_MODEL,
        "input": q,
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [idx],
            }
        ],
    }
    if instructions and instructions.strip():
        payload["instructions"] = instructions.strip()

    headers = {
        "Authorization": f"Bearer {c.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(_responses_url(c), headers=headers, json=payload)
        if resp.status_code != 200:
            logger.warning(
                "bailian generate HTTP %s index=%s body=%s",
                resp.status_code,
                idx,
                resp.text[:300],
            )
            return None
        data = resp.json()
        text = _extract_output_text(data)
        if not text:
            logger.warning("bailian generate empty output index=%s", idx)
            return None
        return text
    except Exception as e:
        logger.warning("bailian generate failed index=%s err=%s", idx, e)
        return None


def generate_stream_sync(
    query: str,
    *,
    index_id: str,
    cfg: BailianConfig | None = None,
    instructions: str | None = None,
    timeout: float = 60,
):
    """SSE 流式生成；yield 文本 delta。"""
    c = cfg or load_bailian_config()
    if not config_ready_for_generate(c):
        return
    idx = (index_id or "").strip()
    q = (query or "").strip()
    if not idx or not q:
        return

    payload: dict[str, Any] = {
        "model": c.generate_model or DEFAULT_GENERATE_MODEL,
        "input": q,
        "stream": True,
        "tools": [{"type": "file_search", "vector_store_ids": [idx]}],
    }
    if instructions and instructions.strip():
        payload["instructions"] = instructions.strip()

    headers = {
        "Authorization": f"Bearer {c.dashscope_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream(
                "POST",
                _responses_url(c),
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    logger.warning(
                        "bailian generate stream HTTP %s index=%s",
                        resp.status_code,
                        idx,
                    )
                    return
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if not chunk or chunk == "[DONE]":
                        continue
                    try:
                        event = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    etype = event.get("type") or ""
                    if etype == "response.output_text.delta":
                        delta = event.get("delta") or ""
                        if delta:
                            yield delta
                    elif etype == "response.completed":
                        break
    except Exception as e:
        logger.warning("bailian generate stream failed index=%s err=%s", idx, e)
