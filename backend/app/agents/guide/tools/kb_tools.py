"""百炼知识库 Agent 工具 — 只读。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.tools import register
from app.core.logger import get_logger
from app.services.bailian.knowledge_chat import knowledge_chat_sync
from app.services.kb_registry import get_kb_registry

logger = get_logger("guide.tools.kb")


@register("list_knowledge_sources")
def list_knowledge_sources(
    _db: Session,
    _child_user_id: int,
    _args: dict | None = None,
) -> dict[str, Any]:
    reg = get_kb_registry()
    return {"sources": reg.list_sources(), "count": len(reg.sources)}


@register("query_knowledge")
def query_knowledge(
    _db: Session,
    _child_user_id: int,
    args: dict | None = None,
) -> dict[str, Any]:
    a = args or {}
    query = str(a.get("query") or "").strip()
    source_key = str(a.get("source_key") or "").strip()
    aid = str(a.get("aid") or "").strip()
    timeout = float(a.get("timeout") or 120)

    if not query:
        return {"ok": False, "error": "query 不能为空"}

    reg = get_kb_registry()
    src = reg.resolve(source_key=source_key or None, aid=aid or None)
    if not src:
        return {"ok": False, "error": "未知知识源，请先 list_knowledge_sources"}

    result = knowledge_chat_sync(query, aid=src.aid, timeout=timeout)
    if not result or not (result.reply or "").strip():
        return {
            "ok": False,
            "error": "knowledge/chat 无有效回复",
            "source_key": src.key,
            "aid": src.aid,
        }

    return {
        "ok": True,
        "reply": result.reply.strip(),
        "source_key": src.key,
        "source_name": src.name,
        "aid": src.aid,
        "request_id": result.request_id,
        "reply_len": len(result.reply),
        "retrieved_doc_count": len(result.retrieved_docs),
    }
