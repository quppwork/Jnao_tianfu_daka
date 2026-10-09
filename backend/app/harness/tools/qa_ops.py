"""答疑侧 MCP 工具：检索 + 会话原文回看。OCR 见 harness/tools/ocr_ops.py（ocr_extract）。"""

from __future__ import annotations

from typing import Any

from app.harness.context import current_context
from app.harness.registry import register_tool
from app.harness.types import ToolSpec


async def qa_reload_passage(args: dict[str, Any]) -> dict[str, Any]:
    """多轮纠错：取本会话题目原文；reocr=true 时对上次拍题图重新 OCR。"""
    from app.agents.qa.memory import load_session_passage, save_session_passage
    from app.db.models import QaSession
    from app.harness.runtime import call_tool
    from app.services.qa_image_store import image_data_url

    ctx = current_context()
    force = bool(args.get("reocr") or args.get("force"))
    image_id = str(args.get("image_id") or ctx.extra.get("last_image_id") or "").strip()
    cached = str(args.get("cached_text") or ctx.extra.get("last_ocr_text") or "").strip()
    session_id = int(args.get("session_id") or ctx.extra.get("qa_session_id") or 0)

    if ctx.db is not None and session_id > 0:
        session = ctx.db.get(QaSession, session_id)
        if session and (not ctx.child_user_id or session.child_user_id == ctx.child_user_id):
            sid, sot = load_session_passage(session)
            if sid:
                image_id = image_id or sid
            if sot:
                cached = cached or sot

    if not force and cached:
        return {
            "ok": True,
            "text": cached,
            "source": "session_cache",
            "image_id": image_id or None,
            "mock": False,
        }

    if not image_id or ctx.child_user_id < 1:
        if cached:
            return {
                "ok": True,
                "text": cached,
                "source": "session_cache",
                "image_id": image_id or None,
                "mock": False,
            }
        return {
            "ok": False,
            "error": "本会话没有可重读的题目图片；请让用户贴原文或重新拍题",
            "mock": False,
        }

    data_url = image_data_url(image_id, ctx.child_user_id)
    if not data_url:
        return {"ok": False, "error": "题目图片不存在或已过期", "mock": False}

    hit = await call_tool(
        "ocr_extract",
        {
            "image_data_url": data_url,
            "max_tokens": int(args.get("max_tokens") or 3500),
            "prompt": str(args.get("prompt") or "").strip()
            or (
                "请完整识别图中题目与阅读材料的全部文字；保持段落换行与题号；"
                "不要编造 Paragraph/行号；不要解题。"
            ),
        },
        profile="qa",
    )
    if not hit.ok:
        return {"ok": False, "error": hit.error or "ocr failed", "mock": False}
    text = str((hit.data or {}).get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "OCR 未识别到文字", "mock": False}

    if ctx.db is not None and session_id > 0:
        session = ctx.db.get(QaSession, session_id)
        if session and (not ctx.child_user_id or session.child_user_id == ctx.child_user_id):
            save_session_passage(session, image_id=image_id, ocr_text=text)
            try:
                ctx.db.commit()
            except Exception:
                ctx.db.rollback()
    ctx.extra["last_image_id"] = image_id
    ctx.extra["last_ocr_text"] = text
    return {
        "ok": True,
        "text": text,
        "source": "reocr",
        "image_id": image_id,
        "provider": (hit.data or {}).get("provider"),
        "mock": bool((hit.data or {}).get("mock")),
    }


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
            name="qa_reload_passage",
            description=(
                "取回本会话题目原文（OCR）。用户指出段落/行号不对、或需要重新定位时调用；"
                "reocr=true 时对上次拍题图重新识别。不要让用户无故重拍。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "reocr": {
                        "type": "boolean",
                        "description": "true=重新识图；false/省略=优先用会话缓存原文",
                    },
                    "force": {"type": "boolean"},
                    "image_id": {"type": "string"},
                    "session_id": {"type": "integer"},
                    "max_tokens": {"type": "integer"},
                    "prompt": {"type": "string"},
                },
                "additionalProperties": False,
            },
            handler=qa_reload_passage,
            permission="readonly",
            profiles=("qa",),
            plane="host",
            mcp_server="jnao-host",
            needs_db=True,
        )
    )
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
