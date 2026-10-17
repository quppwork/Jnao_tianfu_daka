"""成人报告天赋解答 — talent_doc 检索工具（契约化，只检索不生成）。"""

from __future__ import annotations

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

    try:
        from app.services.bailian.retrieve import retrieve_sync

        result = retrieve_sync(query, index_id=TALENT_DOC_INDEX_ID, top_n=top_n)
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
    return payload


SPEC = ToolSpec(
    name="talent_doc_retrieve",
    description=(
        "检索 Jinao 天赋知识库（talent_doc / x1micrdmjq）切片，供你据此作答。"
        "适用：用户问五者/天赋含义、练法、课程、报告相关事实。"
        "不适用：打招呼、寒暄、确认身份——此时不要调用本工具，直接口头回应。"
        "只返回原文片段，不生成对用户的最终答复；库外问题不要调用。"
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
