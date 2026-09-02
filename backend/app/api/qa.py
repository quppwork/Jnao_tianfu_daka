"""学科答疑 API"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_db
from app.core.biz_log import biz_event, biz_timer
from app.core.rate_limit import check_qa_chat_limits
from app.core.security import is_debug_routes_enabled
from app.core.sse import SSE_HEADERS, emit_event_stream, sse_done, sse_json
from app.services import qa_service
from app.services.qa_image_store import get_qa_image, save_qa_image

router = APIRouter(prefix="/api/qa", tags=["qa"])

_IMAGE_RESPONSE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Disposition": "inline",
    "Cache-Control": "private, max-age=3600",
}


@router.get("/debug")
async def qa_debug():
    if not is_debug_routes_enabled():
        raise HTTPException(404, "Not Found")
    from app.agents.qa.trace import get_qa_trace_metrics
    from app.services.doubao_client import is_configured
    from config.loader import load_settings

    c = load_settings().get("doubao", {})
    return {
        "provider": "doubao",
        "model": c.get("model"),
        "key_ok": is_configured(),
        "trace_metrics": get_qa_trace_metrics(),
    }


class QaChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: int | None = Field(None, ge=1)
    subject: str | None = Field(None, max_length=20, description="数学/语文/英语/科学")
    image_id: str | None = Field(None, max_length=64)
    use_rag: bool | None = Field(None, description="是否检索教学法知识库")


class QaSessionCreateRequest(BaseModel):
    subject: str | None = Field(None, max_length=20)


@router.post("/chat")
async def qa_chat(
    req: QaChatRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    check_qa_chat_limits(child_user_id)
    with biz_timer(
        "qa.chat",
        session_id=req.session_id,
        subject=req.subject or "-",
        msg_len=len(req.message or ""),
        has_image=bool(req.image_id),
    ) as ctx:
        try:
            return await qa_service.chat(
                db,
                child_user_id,
                req.message,
                session_id=req.session_id,
                subject=req.subject,
                image_id=req.image_id,
                use_rag=req.use_rag,
            )
        except ValueError as e:
            ctx["result"] = "not_found"
            ctx["level"] = "warning"
            raise HTTPException(404, str(e)) from e


@router.post("/chat/stream")
async def qa_chat_stream(
    req: QaChatRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """SSE 流式学科答疑"""
    check_qa_chat_limits(child_user_id)
    biz_event(
        "qa.chat_stream",
        result="start",
        session_id=req.session_id,
        subject=req.subject or "-",
        msg_len=len(req.message or ""),
    )

    async def events():
        try:
            async for chunk in emit_event_stream(
                qa_service.chat_stream(
                    db,
                    child_user_id,
                    req.message,
                    session_id=req.session_id,
                    subject=req.subject,
                    image_id=req.image_id,
                    use_rag=req.use_rag,
                )
            ):
                yield chunk
            biz_event("qa.chat_stream", result="ok")
        except ValueError as e:
            biz_event("qa.chat_stream", result="not_found", level="warning")
            yield sse_json({"type": "error", "message": str(e)})
            yield sse_done()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/upload-image")
async def qa_upload_image(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    del db
    raw = await file.read()
    result = save_qa_image(child_user_id, file.filename or "photo.jpg", raw, "")
    return result


@router.get("/images/{image_id}")
def qa_get_image(
    image_id: str,
    child_user_id: int = Depends(get_authenticated_student),
):
    meta = get_qa_image(image_id, child_user_id)
    if not meta:
        raise HTTPException(404, "图片不存在")
    path = Path(meta["path"])
    if not path.is_file():
        raise HTTPException(404, "图片文件不存在")
    return FileResponse(
        path,
        media_type=meta.get("content_type") or "image/jpeg",
        headers=_IMAGE_RESPONSE_HEADERS,
    )


@router.get("/sessions")
def list_sessions(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return {"items": qa_service.list_sessions(db, child_user_id)}


@router.post("/sessions")
def create_session(
    req: QaSessionCreateRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    session = qa_service.create_session(db, child_user_id, req.subject)
    return {"id": session.id, "subject": session.subject}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    messages = qa_service.get_session_messages(db, session_id, child_user_id)
    if messages is None:
        raise HTTPException(404, "会话不存在")
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    if not qa_service.delete_session(db, session_id, child_user_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}
