"""AI 对话 API — 流式 & 非流式代理"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api import ai_proxy

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Request models ──

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = "mobile_user"
    user_department: str = ""
    history: list[dict] | None = None


# ── Non-streaming chat ──

@router.post("")
async def chat(req: ChatRequest):
    """非流式对话 — 代理到 tianfu_rag"""
    try:
        result = await ai_proxy.chat(
            message=req.message,
            user_id=req.user_id,
            user_department=req.user_department,
            history=req.history,
        )
        return {"code": 1, "data": result}
    except Exception as e:
        return {"code": 0, "data": {"answer": f"AI 服务暂不可用：{e}", "sources": [], "answer_mode": "error"}}


# ── Streaming chat (SSE) ──

@router.get("/stream")
async def stream_chat(
    message: str = Query(...),
    user_id: str = Query("mobile_user"),
):
    """SSE 流式对话 — 代理到 tianfu_rag"""

    async def event_stream():
        try:
            async for event in ai_proxy.proxy_talent_stream(message=message, user_id=user_id):
                event_type = event.get("type", "token")
                if event_type == "token":
                    yield f"data: {event['content']}\n\n"
                elif event_type == "done":
                    yield "data: [DONE]\n\n"
                    break
                elif event_type == "error":
                    yield f"data: [ERROR] {event.get('message', '')}\n\n"
                    break
        except Exception as e:
            yield f"data: [ERROR] AI 服务连接失败：{e}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
