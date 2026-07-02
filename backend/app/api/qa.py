"""学科答疑 API"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.services import qa_service
from app.services.qa_image_store import get_qa_image, save_qa_image

router = APIRouter(prefix="/api/qa", tags=["qa"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


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
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
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
        raise HTTPException(404, str(e)) from e


@router.post("/upload-image")
async def qa_upload_image(
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "仅支持 JPEG/PNG/WebP/GIF 图片")
    raw = await file.read()
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise HTTPException(400, "图片为空或超过 8MB")
    result = save_qa_image(child_user_id, file.filename or "photo.jpg", raw, content_type or "image/jpeg")
    return result


@router.get("/images/{image_id}")
def qa_get_image(
    image_id: str,
    child_user_id: int = Depends(get_authenticated_user),
):
    meta = get_qa_image(image_id, child_user_id)
    if not meta:
        raise HTTPException(404, "图片不存在")
    path = Path(meta["path"])
    if not path.is_file():
        raise HTTPException(404, "图片文件不存在")
    return FileResponse(path, media_type=meta.get("content_type") or "image/jpeg")


@router.get("/sessions")
def list_sessions(
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return {"items": qa_service.list_sessions(db, child_user_id)}


@router.post("/sessions")
def create_session(
    req: QaSessionCreateRequest,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    session = qa_service.create_session(db, child_user_id, req.subject)
    return {"id": session.id, "subject": session.subject}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    messages = qa_service.get_session_messages(db, session_id, child_user_id)
    if messages is None:
        raise HTTPException(404, "会话不存在")
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if not qa_service.delete_session(db, session_id, child_user_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}
