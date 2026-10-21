"""成人报告天赋解答 — talent_doc 检索工具（契约化，只检索不生成）。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.harness.rag_contract import (
    TALENT_DOC_INDEX_ID,
    TALENT_DOC_RETRIEVE_INPUT,
    TALENT_DOC_SOURCE_KEY,
    fail_payload,
    validate_talent_doc_input,
    validate_talent_doc_output,
)
from app.harness.registry import register_tool
from app.harness.types import ToolSpec
from app.model_cost import AgentFeature, CostEvent, get_cost_recorder
from app.services.report_talent_sections import sections_from_hits


# 成功结果的进程内短缓存：(query, top_n) → (时间戳, payload)；失败不缓存
_CACHE: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_S = 300.0
_CACHE_MAX = 128


async def talent_doc_retrieve(args: dict[str, Any]) -> dict[str, Any]:
    violation = validate_talent_doc_input(args)
    if violation:
        return fail_payload(
            query=str((args or {}).get("query") or ""),
            error=violation.as_text(),
            error_kind="contract_input",
        )

    query = str(args.get("query") or "").strip()
    top_n = int(args.get("top_n") or 3)
    top_n = max(1, min(8, top_n))

    cached = _CACHE.get((query, top_n))
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_S:
        return cached[1]

    # SDK 是阻塞调用：走 async 包装（线程池 + 超时），不卡事件循环
    from app.services.bailian.retrieve import retrieve as retrieve_async

    try:
        result = await retrieve_async(query, index_id=TALENT_DOC_INDEX_ID, top_n=top_n)
    except asyncio.TimeoutError:
        get_cost_recorder().record(
            CostEvent(
                provider="bailian",
                feature=AgentFeature.REPORT_TALENT,
                api="retrieve",
                model=TALENT_DOC_INDEX_ID,
                metric_kind="est_rag",
                call_count=1,
                ok=False,
                meta={"error": "TimeoutError"},
            )
        )
        return fail_payload(
            query=query,
            error="retrieve timeout",
            error_kind="timeout",
        )
    except Exception as e:
        get_cost_recorder().record(
            CostEvent(
                provider="bailian",
                feature=AgentFeature.REPORT_TALENT,
                api="retrieve",
                model=TALENT_DOC_INDEX_ID,
                metric_kind="est_rag",
                call_count=1,
                ok=False,
                meta={"error": type(e).__name__},
            )
        )
        return fail_payload(
            query=query,
            error=f"retrieve failed: {type(e).__name__}",
            error_kind="runtime",
        )

    if result is None:
        return fail_payload(
            query=query,
            error="bailian retrieve 未配置或返回空",
            error_kind="runtime",
        )

    hits: list[dict[str, Any]] = []
    for node in list(result.nodes or [])[:top_n]:
        text = str(getattr(node, "text", "") or "").strip()
        if not text:
            continue
        hits.append(
            {
                "text": text[:1200],
                "score": getattr(node, "score", None),
                "doc_name": str(getattr(node, "doc_name", "") or ""),
                "title": str(getattr(node, "title", "") or ""),
                "doc_id": str(getattr(node, "doc_id", "") or ""),
            }
        )

    if not hits:
        payload = fail_payload(
            query=query,
            error="知识库无命中",
            error_kind="empty",
        )
        if result.request_id:
            payload["request_id"] = str(result.request_id)
        out_err = validate_talent_doc_output(payload)
        if out_err:
            payload["error"] = out_err.as_text()
            payload["error_kind"] = "contract_output"
        return payload

    payload = {
        "ok": True,
        "source_key": TALENT_DOC_SOURCE_KEY,
        "index_id": TALENT_DOC_INDEX_ID,
        "query": query,
        "hit_count": len(hits),
        "hits": hits,
        # 命中的报告章节：门面据此出引用，不再猜正文关键词
        "citations": sections_from_hits(hits),
    }
    if result.request_id:
        payload["request_id"] = str(result.request_id)
    out_err = validate_talent_doc_output(payload)
    if out_err:
        return fail_payload(
            query=query,
            error=out_err.as_text(),
            error_kind="contract_output",
        )
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[(query, top_n)] = (time.monotonic(), payload)
    return payload


SPEC = ToolSpec(
    name="talent_doc_retrieve",
    description=(
        "检索 Jinao 天赋知识库（talent_doc / ockqxuuru1）切片。"
        "只返回原文片段，不生成对用户的最终答复。"
        "报告天赋解答由门面每问必调；有命中才注入上下文，无命中走统一拒答。"
    ),
    input_schema=TALENT_DOC_RETRIEVE_INPUT,
    handler=talent_doc_retrieve,
    isolation="none",
    permission="readonly",
    profiles=("report_talent",),
    plane="host",
    mcp_server="jnao-host",
)


def register() -> None:
    register_tool(SPEC)


register()
