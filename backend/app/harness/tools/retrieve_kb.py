"""共享百炼 Retrieve — Guide / Consult / 后续 Parent 共用，不走 knowledge/chat 直答。"""

from __future__ import annotations

from typing import Any

from app.harness.registry import register_tool
from app.harness.types import ToolSpec


async def retrieve_kb(args: dict[str, Any]) -> dict[str, Any]:
    from app.services.bailian import guide_rag_query
    from app.services.brain_edu_kb import FOUNDATION, local_retrieve

    query = str(args.get("query") or "").strip()
    timeout = float(args.get("timeout") or 25)
    prefer_raw = args.get("prefer_docs") or args.get("docs")
    prefer_docs: list[str] | None = None
    if isinstance(prefer_raw, str) and prefer_raw.strip():
        prefer_docs = [x.strip() for x in prefer_raw.split(",") if x.strip()]
    elif isinstance(prefer_raw, list):
        prefer_docs = [str(x).strip() for x in prefer_raw if str(x).strip()]
    if not prefer_docs:
        prefer_docs = list(FOUNDATION)

    if not query:
        return {"ok": False, "error": "query 不能为空", "rag_used": False}

    rag = await guide_rag_query(query, timeout=timeout)
    if rag and (rag.rag_block or "").strip():
        hits: list[dict[str, Any]] = []
        for n in (rag.nodes or [])[:5]:
            hits.append(
                {
                    "score": getattr(n, "score", None),
                    "text": (getattr(n, "text", None) or "")[:240],
                    "doc": getattr(n, "title", None) or getattr(n, "doc_name", None) or "",
                }
            )
        sources = list(getattr(rag, "sources", None) or [])
        if not sources:
            sources = [h["doc"] for h in hits if h.get("doc")]
        return {
            "ok": True,
            "rag_used": True,
            "rag_block": rag.rag_block.strip(),
            "kb_hits": hits,
            "sources": sources,
            "query": query,
            "mode": getattr(rag, "mode", None) or "bailian",
        }

    # 百炼未命中 → 本地 01/02/03（及同目录其它 md）
    return local_retrieve(query, prefer_docs=prefer_docs)


SPEC = ToolSpec(
    name="retrieve_kb",
    description="从与引导页相同的百炼知识库 Retrieve 切片（不直答）。",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索问句"},
            "timeout": {"type": "number", "description": "秒，默认 25"},
            "prefer_docs": {
                "type": "string",
                "description": "优先文档，逗号分隔；天赋咨询默认 01/02/03",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    handler=retrieve_kb,
    isolation="none",
    permission="readonly",
    profiles=(
        "guide",
        "parent_guide",
        "consult",
        "qa",
        "solve_science",
        "solve_language",
        "solve_humanities",
        "solve_invention",
        "solve_arts",
    ),
    plane="host",
    mcp_server="jnao-host",
)


def register() -> None:
    register_tool(SPEC)


register()
