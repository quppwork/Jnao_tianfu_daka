"""学科答疑 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.services import qa_service

router = APIRouter(prefix="/api/qa", tags=["qa"])


class QaChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: int | None = None
    subject: str | None = Field(None, description="数学/语文/英语/科学")


class QaSessionCreateRequest(BaseModel):
    subject: str | None = None


@router.post("/chat")
async def qa_chat(
    req: QaChatRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return await qa_service.chat(
            db,
            child_user_id,
            req.message,
            session_id=req.session_id,
            subject=req.subject,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/sessions")
def list_sessions(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return {"items": qa_service.list_sessions(db, child_user_id)}


@router.post("/sessions")
def create_session(
    req: QaSessionCreateRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    session = qa_service.create_session(db, child_user_id, req.subject)
    return {"id": session.id, "subject": session.subject}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    messages = qa_service.get_session_messages(db, session_id, child_user_id)
    if messages is None:
        raise HTTPException(404, "会话不存在")
    return {"session_id": session_id, "messages": messages}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    if not qa_service.delete_session(db, session_id, child_user_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}
