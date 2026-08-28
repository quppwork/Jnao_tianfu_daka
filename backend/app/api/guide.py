"""首页引导对话 — 豆包 AI + 会话持久化"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_db
from app.core.logger import get_logger
from app.core.rate_limit import check_guide_chat_limits
from app.core.security import is_debug_routes_enabled
from app.core.sse import SSE_HEADERS, emit_event_stream, sse_done, sse_json
from app.services import guide_service
from app.services.doubao_client import is_configured

logger = get_logger("guide")

router = APIRouter(prefix="/api/guide", tags=["guide"])


class GuideChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: int | None = Field(None, ge=1)


class GuideBootstrapRequest(BaseModel):
    force: bool = False
    use_llm: bool = True


class GuideKbDebugQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    source_key: str | None = Field(
        None, description="kb_registry 中的 key，如 video_practice / talent_doc"
    )
    aid: str | None = Field(None, description="直接指定 aid-*，优先于 source_key")
    timeout: float = Field(90, ge=10, le=180)


class GuideConfirmRequest(BaseModel):
    write_op: str = Field(..., min_length=1, max_length=64)
    args: dict = Field(default_factory=dict)


@router.get("/debug")
async def guide_debug():
    if not is_debug_routes_enabled():
        raise HTTPException(404, "Not Found")
    from config.loader import load_settings
    from app.agents.guide.trace import get_guide_trace_metrics
    from app.agents.guide.writes import list_write_ops
    from app.services.bailian import bailian_status
    from app.agents.guide.kb_agent import guide_kb_agent_ready

    c = load_settings().get("doubao", {})
    return {
        "provider": "doubao",
        "model": c.get("model"),
        "key_ok": is_configured(),
        "base": c.get("api_base"),
        "kb_agent_ready": guide_kb_agent_ready(),
        "trace_metrics": get_guide_trace_metrics(),
        "write_ops": list_write_ops(),
        "bailian_rag": bailian_status(),
    }


@router.get("/debug/kb/sources")
async def guide_debug_kb_sources():
    """P0：列出可调用知识源（Agent 目录）。"""
    if not is_debug_routes_enabled():
        raise HTTPException(404, "Not Found")
    from app.services.kb_registry import get_kb_registry

    reg = get_kb_registry()
    return {"sources": reg.list_sources(), "count": len(reg.sources)}


@router.post("/debug/kb/query")
async def guide_debug_kb_query(req: GuideKbDebugQueryRequest):
    """P0：裸调百炼 knowledge/chat，不叠加代码侧人设/策略/模板。"""
    if not is_debug_routes_enabled():
        raise HTTPException(404, "Not Found")
    import asyncio

    from app.services.bailian.knowledge_chat import knowledge_chat_sync
    from app.services.kb_registry import get_kb_registry

    reg = get_kb_registry()
    src = reg.resolve(source_key=req.source_key, aid=req.aid)
    if not src and req.aid:
        aid = req.aid.strip()
        source_key = None
        source_name = None
    elif src:
        aid = src.aid
        source_key = src.key
        source_name = src.name
    else:
        raise HTTPException(
            400,
            "请提供 source_key（video_practice / talent_doc）或 aid",
        )

    result = await asyncio.to_thread(
        knowledge_chat_sync,
        req.query,
        aid=aid,
        timeout=req.timeout,
    )
    if result is None:
        raise HTTPException(
            502,
            "knowledge/chat 调用失败（检查 DASHSCOPE_API_KEY、aid 是否已发布、网络/超时）",
        )

    return {
        "source_key": source_key,
        "source_name": source_name,
        "aid": aid,
        "query": req.query,
        **result.to_public_dict(),
        "reply": result.reply,
        "retrieved_docs_preview": [
            {
                "doc_name": d.doc_name,
                "score": d.score,
                "text_preview": (d.text[:200] + "…") if len(d.text) > 200 else d.text,
            }
            for d in result.retrieved_docs[:5]
        ],
    }


@router.get("/session")
def guide_session(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return guide_service.load_session_payload(db, child_user_id)


@router.get("/sessions")
def guide_sessions(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return {"items": guide_service.list_sessions(db, child_user_id)}


@router.get("/sessions/{session_id}")
def guide_session_detail(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    payload = guide_service.get_session_payload(db, child_user_id, session_id)
    if payload is None:
        raise HTTPException(404, "会话不存在")
    return payload


@router.delete("/sessions/{session_id}")
def guide_session_delete(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    if not guide_service.delete_session(db, child_user_id, session_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


@router.post("/bootstrap")
async def guide_bootstrap(
    req: GuideBootstrapRequest = GuideBootstrapRequest(),
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """进首页开场：按情境返回欢迎语（模板保底，可选 LLM）。"""
    result = await guide_service.bootstrap(
        db,
        child_user_id,
        force=req.force,
        use_llm=req.use_llm,
    )
    logger.info(
        f"Guide bootstrap uid={child_user_id} situation={result.get('situation')} "
        f"source={result.get('source')}"
    )
    return result


@router.post("/clear")
def guide_clear(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    cleared = guide_service.clear_sessions(db, child_user_id)
    return {"cleared": cleared}


@router.post("/confirm")
def guide_confirm_write(
    req: GuideConfirmRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """R5：确认卡二次确认后落库；白名单外写操作直接拒绝。"""
    result = guide_service.confirm_write(
        db,
        child_user_id,
        write_op=req.write_op,
        args=req.args or {},
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "写操作失败")
    return result


@router.post("/chat")
async def guide_chat(
    req: GuideChatRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    check_guide_chat_limits(child_user_id)
    if not is_configured():
        return {"reply": "AI 服务未配置，请先设置豆包 API Key。", "session_id": req.session_id}

    result = await guide_service.chat(
        db, child_user_id, req.message, session_id=req.session_id
    )
    logger.info(f"Guide chat uid={child_user_id}: {req.message[:30]}...")
    return result


@router.post("/chat/stream")
async def guide_chat_stream(
    req: GuideChatRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """SSE 流式引导对话"""
    check_guide_chat_limits(child_user_id)

    async def events():
        if not is_configured():
            yield sse_json({"type": "error", "message": "AI 服务未配置，请先设置豆包 API Key。"})
            yield sse_done()
            return
        async for chunk in emit_event_stream(
            guide_service.chat_stream(
                db, child_user_id, req.message, session_id=req.session_id
            )
        ):
            yield chunk

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)

