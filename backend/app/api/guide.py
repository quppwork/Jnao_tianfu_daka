"""首页引导对话 — 豆包 AI + 会话持久化"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.core.logger import get_logger
from app.core.security import is_debug_routes_enabled
from app.services import guide_service
from app.services.doubao_client import is_configured

logger = get_logger("guide")

router = APIRouter(prefix="/api/guide", tags=["guide"])


class GuideChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: int | None = Field(None, ge=1)


@router.get("/debug")
async def guide_debug():
    if not is_debug_routes_enabled():
        raise HTTPException(404, "Not Found")
    from config.loader import load_settings

    c = load_settings().get("doubao", {})
    return {
        "provider": "doubao",
        "model": c.get("model"),
        "key_ok": is_configured(),
        "base": c.get("api_base"),
    }


@router.get("/session")
def guide_session(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return guide_service.load_session_payload(db, child_user_id)


@router.post("/chat")
async def guide_chat(
    req: GuideChatRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    if not is_configured():
        return {"reply": "AI 服务未配置，请先设置豆包 API Key。", "session_id": req.session_id}

    result = await guide_service.chat(
        db, child_user_id, req.message, session_id=req.session_id
    )
    logger.info(f"Guide chat uid={child_user_id}: {req.message[:30]}...")
    return result
