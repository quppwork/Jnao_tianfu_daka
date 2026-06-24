"""AI 对话 API — 统一走豆包 Ark"""

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.doubao_client import chat_completion, chat_completion_stream, is_configured

router = APIRouter(prefix="/api/chat", tags=["chat"])

CHAT_SYSTEM = """你是 JNAO 天赋成长平台的 AI 助手。
可回答平台使用、学习方法、天赋成长相关问题。
语气亲切，回答简洁实用。"""


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = "mobile_user"
    user_department: str = ""
    history: list[dict] | None = None


@router.post("")
async def chat(req: ChatRequest):
    """非流式对话 — 豆包"""
    if not is_configured():
        return {
            "code": 0,
            "data": {"answer": "AI 服务未配置豆包 API Key", "sources": [], "answer_mode": "error"},
        }
    try:
        answer = await chat_completion(
            system_prompt=CHAT_SYSTEM,
            user_message=req.message,
            history=req.history,
            max_tokens=800,
        )
        if not answer:
            raise RuntimeError("豆包返回空响应")
        return {
            "code": 1,
            "data": {"answer": answer, "sources": [], "answer_mode": "doubao"},
        }
    except Exception as e:
        return {
            "code": 0,
            "data": {"answer": f"AI 服务暂不可用：{e}", "sources": [], "answer_mode": "error"},
        }


@router.get("/stream")
async def stream_chat(
    message: str = Query(...),
    user_id: str = Query("mobile_user"),
):
    """SSE 流式对话 — 豆包"""

    async def event_stream():
        if not is_configured():
            yield "data: [ERROR] 豆包 API 未配置\n\n"
            return
        try:
            async for token in chat_completion_stream(
                system_prompt=CHAT_SYSTEM,
                user_message=message,
                max_tokens=800,
            ):
                if token.startswith("[ERROR]"):
                    yield f"data: {token}\n\n"
                    break
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] AI 服务连接失败：{e}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
