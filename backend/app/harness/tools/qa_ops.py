"""答疑侧 MCP 工具：检索。OCR 见 harness/tools/ocr_ops.py（ocr_extract）。"""

from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec


async def retrieve_qa_kb(args: dict[str, Any]) -> dict[str, Any]:
    from app.services.qa_kb_retrieve import retrieve_qa_method_kb

    query = str(args.get("query") or "").strip()
    subject = str(args.get("subject") or "").strip() or None
    if not query:
        return {"ok": False, "error": "query 不能为空", "rag_used": False}
    hit = await retrieve_qa_method_kb(
        query,
        subject=subject,
        timeout=float(args.get("timeout") or 20),
    )
    if not hit or not hit.get("answer"):
        return {"ok": True, "rag_used": False, "rag_context": "", "rag_sources": []}
    return {
        "ok": True,
        "rag_used": True,
        "rag_context": hit["answer"],
        "rag_sources": list(hit.get("sources") or []),
        "rag_source": hit.get("rag_source") or "bailian_method",
        "rag_kind": "method",
    }


async def retrieve_qa_legacy(args: dict[str, Any]) -> dict[str, Any]:
    from app.services.qa_rag_client import rag_chat

    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空", "rag_used": False}
    uid = str(args.get("user_id") or "child_0")
    subject = str(args.get("subject") or "").strip() or None
    rag = await rag_chat(query, user_id=uid, subject=subject)
    if not rag or not rag.get("answer"):
        return {"ok": True, "rag_used": False, "rag_context": "", "rag_sources": []}
    return {
        "ok": True,
        "rag_used": True,
        "rag_context": rag["answer"],
        "rag_sources": list(rag.get("sources") or []),
        "rag_source": "tianfu_rag",
        "rag_kind": "legacy",
    }


def register() -> None:
    register_tool(
        ToolSpec(
            name="retrieve_qa_kb",
            description="答疑百炼练法库检索（不直答）。",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "subject": {"type": "string"},
                    "timeout": {"type": "number"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=retrieve_qa_kb,
            permission="readonly",
            profiles=("qa",),
            plane="host",
            mcp_server="jnao-host",
        )
    )
    register_tool(
        ToolSpec(
            name="retrieve_qa_legacy",
            description="答疑旧教学法 RAG。",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "user_id": {"type": "string"},
                    "subject": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=retrieve_qa_legacy,
            permission="readonly",
            profiles=("qa",),
            plane="host",
            mcp_server="jnao-host",
        )
    )
