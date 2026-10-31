"""在线咨询 API — 业务库 SoT + WebSocket 实时；OpenIM 可选。"""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.services import consult_service, consult_ws

logger = logging.getLogger("jnao.consult")

router = APIRouter(prefix="/api/parent/consult", tags=["consult"])


def _require_parent_id(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> int:
    from app.core.biz_log import bind_user
    from app.services import auth_service

    user = auth_service.get_child_user(db, user_id)
    if not user or user.role != auth_service.ROLE_PARENT:
        raise HTTPException(403, "需要家长账号")
    bind_user(user_id, role=auth_service.ROLE_PARENT)
    return user_id


class OpenConversationRequest(BaseModel):
    channel_code: str = Field(..., min_length=1, max_length=64)
    child_id: int | None = Field(None, ge=1)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    client_msg_id: str | None = Field(None, max_length=64)
    content_type: str = Field("text", max_length=16)


class BoardPostRequest(BaseModel):
    channel_code: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=2000)
    conversation_id: int | None = Field(None, ge=1)


class ImCallbackRequest(BaseModel):
    im_msg_id: str = Field(..., min_length=1, max_length=128)
    im_conversation_id: str | None = None
    sender_im_user_id: str | None = None
    content: str = ""
    content_type: str = "text"
    raw: dict | None = None


def _auth_parent_ws(db: Session, user_id: int, token: str) -> None:
    from app.db.models import ChildUser
    from app.services import auth_service
    from app.services.auth_service import is_account_active
    from app.services.session_service import validate_session

    if user_id < 1 or not token:
        raise HTTPException(401, "需要 user_id 与 token")
    user = db.get(ChildUser, user_id)
    if not user or not is_account_active(user):
        raise HTTPException(401, "用户无效")
    if user.role != auth_service.ROLE_PARENT:
        raise HTTPException(403, "需要家长账号")
    if not validate_session(db, user_id, token):
        raise HTTPException(401, "会话失效，请重新登录")


@router.websocket("/ws")
async def consult_websocket(
    websocket: WebSocket,
    user_id: int = Query(..., ge=1),
    token: str = Query(..., min_length=8),
):
    """家长实时通道。ws://.../api/parent/consult/ws?user_id=&token="""
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        try:
            _auth_parent_ws(db, user_id, token.strip())
        except HTTPException as e:
            await websocket.close(code=4401, reason=str(e.detail)[:120])
            return
    finally:
        db.close()

    await consult_ws.hub.connect(user_id, websocket)
    await websocket.send_json(
        {"type": "hello", "realtime": "websocket", "user_id": user_id}
    )
    try:
        while True:
            raw = await websocket.receive_json()
            if not isinstance(raw, dict):
                continue
            t = raw.get("type")
            if t == "ping":
                await websocket.send_json({"type": "pong"})
            elif t == "subscribe":
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "conversation_id": raw.get("conversation_id"),
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("consult ws loop error uid=%s", user_id)
    finally:
        consult_ws.hub.disconnect(user_id, websocket)


@router.get("/channels")
def get_channels(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    items = [consult_service.channel_to_dict(c) for c in consult_service.list_channels(db)]
    group_bar = None
    dayu = next((c for c in items if c["code"] == "dayu"), None)
    if dayu:
        # 打开共享群后才有准确人数；此处尝试读共享会话
        from sqlalchemy import select

        from app.db.models import ConsultConversation

        shared = db.scalars(
            select(ConsultConversation).where(
                ConsultConversation.channel_id == dayu["id"],
                ConsultConversation.kind == "group",
                ConsultConversation.parent_user_id == 0,
                ConsultConversation.status != "closed",
            )
        ).first()
        n = consult_service.count_parent_members(db, shared.id) if shared else 0
        online = 0
        if shared:
            mids = consult_service.list_parent_member_ids(db, shared.id)
            online = consult_ws.hub.online_among(mids)
        group_bar = {
            "title": "天赋家长交流群",
            "members": f"群成员 {n}" if n else "进入后加入群聊",
            "live": f"{online} 人在线" if online else None,
        }
    _ = user_id
    return {
        "channels": items,
        "realtime": "websocket",
        "ws_path": "/api/parent/consult/ws",
        "duty": None,
        "group_bar": group_bar,
        "im_configured": consult_service.im_configured(),
        "openim_optional": True,
        "my_display_name": consult_service.parent_display_name(db, user_id),
    }


@router.get("/conversations")
def get_conversations(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    from app.db.models import ConsultChannel

    convs = consult_service.list_conversations(db, user_id)
    channel_ids = {c.channel_id for c in convs}
    channels = {
        ch.id: ch
        for ch in consult_service.list_channels(db)
        if ch.id in channel_ids
    }
    missing = channel_ids - set(channels)
    if missing:
        for ch in db.scalars(select(ConsultChannel).where(ConsultChannel.id.in_(missing))):
            channels[ch.id] = ch
    return {
        "conversations": [
            consult_service.conversation_to_dict(c, channels.get(c.channel_id), db=db)
            for c in convs
        ]
    }


@router.post("/conversations/open")
def open_conversation(
    req: OpenConversationRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    try:
        conv, channel, created = consult_service.open_conversation(
            db,
            parent_user_id=user_id,
            channel_code=req.channel_code.strip(),
            child_user_id=req.child_id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {
        "created": created,
        "conversation": consult_service.conversation_to_dict(conv, channel, db=db),
        "channel": consult_service.channel_to_dict(channel),
    }


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    after_id: int | None = None,
    limit: int = 50,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from app.db.models import ConsultChannel

    conv = consult_service.get_accessible_conversation(
        db, conversation_id=conversation_id, parent_user_id=user_id
    )
    if not conv:
        raise HTTPException(404, "会话不存在")
    channel = db.get(ConsultChannel, conv.channel_id)
    msgs = consult_service.list_messages(
        db, conversation_id=conversation_id, after_id=after_id, limit=limit
    )
    if conv.unread_parent:
        conv.unread_parent = 0
        db.commit()
    cache: dict[int, str] = {}
    return {
        "messages": [
            consult_service.message_to_dict(
                m, viewer_user_id=user_id, channel=channel, db=db, name_cache=cache
            )
            for m in msgs
        ]
    }


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    req: SendMessageRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    from app.db.models import ConsultChannel
    from app.agents import consult as consult_agent

    conv = consult_service.get_accessible_conversation(
        db, conversation_id=conversation_id, parent_user_id=user_id
    )
    if not conv:
        raise HTTPException(404, "会话不存在")
    if conv.status == "closed":
        raise HTTPException(400, "会话已关闭")

    channel = db.get(ConsultChannel, conv.channel_id)
    user_msg, existing_bot = consult_service.send_parent_message(
        db,
        conversation=conv,
        parent_user_id=user_id,
        content=req.content,
        client_msg_id=req.client_msg_id,
        content_type=req.content_type,
        run_agent=False,
    )
    db.commit()

    member_ids = consult_service.list_parent_member_ids(db, conv.id)
    if user_id not in member_ids:
        member_ids.append(user_id)

    def _dict(m):
        return consult_service.message_to_dict(
            m, viewer_user_id=user_id, channel=channel, db=db
        )

    # 扇出时每人视角不同（is_me / sender_name），按接收者分别打包
    for mid in member_ids:
        payload = consult_service.message_to_dict(
            user_msg, viewer_user_id=mid, channel=channel, db=db
        )
        consult_ws.publish_message_new(
            parent_user_id=mid, conversation_id=conversation_id, message=payload
        )

    out: dict = {"message": _dict(user_msg)}

    if existing_bot:
        b = _dict(existing_bot)
        out["bot_message"] = b
        return out

    if not channel or not consult_service.should_auto_agent(channel, req.content):
        return out

    # 群聊只由大宇应答；@其他顾问时在回复里引导去单独咨询
    reply_channel = channel
    specialty = []
    if channel.kind == "group":
        dayu = consult_service.get_channel_by_code(db, "dayu")
        if dayu and dayu.ai_enabled:
            reply_channel = dayu
        specialty = consult_service.mentioned_specialty_channels(db, req.content)

    job = consult_service.enqueue_agent_job(
        db,
        conversation_id=conv.id,
        trigger_msg_id=user_msg.id,
        process_inline=False,
    )
    job.status = "running"
    job.started_at = datetime.utcnow()
    db.commit()

    result = await consult_agent.generate_consult_reply(
        db,
        conversation=conv,
        channel=reply_channel,
        user_text=req.content,
        parent_user_id=user_id,
        trigger_msg_id=user_msg.id,
        specialty_channels=specialty,
        group_room=(channel.kind == "group"),
    )
    bot_msg = consult_service.append_bot_message(
        db,
        conversation=conv,
        content=result["reply"],
        reply_to_id=user_msg.id,
        meta={
            "job_id": job.id,
            "intent": result.get("intent"),
            "rag_used": result.get("rag_used"),
            "model": result.get("model"),
            "for_parent_id": user_id,
            "history_turns": result.get("history_turns"),
            "persona_code": reply_channel.code,
            "persona_title": reply_channel.title,
            "redirect_codes": [c.code for c in specialty],
        },
    )
    consult_service.finish_agent_job(
        db,
        job,
        result_msg_id=bot_msg.id,
        intent=result.get("intent"),
        model=result.get("model"),
        kb_hits=result.get("kb_hits"),
        error=result.get("error"),
    )
    db.commit()

    for mid in member_ids:
        payload = consult_service.message_to_dict(
            bot_msg, viewer_user_id=mid, channel=channel, db=db
        )
        consult_ws.publish_message_new(
            parent_user_id=mid, conversation_id=conversation_id, message=payload
        )

    out["bot_message"] = _dict(bot_msg)
    out["rag_used"] = bool(result.get("rag_used"))
    return out


@router.post("/board")
def post_board(
    req: BoardPostRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    try:
        post = consult_service.create_board_post(
            db,
            parent_user_id=user_id,
            channel_code=req.channel_code.strip(),
            body=req.body,
            conversation_id=req.conversation_id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    pdata = consult_service.board_to_dict(post)
    consult_ws.publish_board_updated(
        parent_user_id=user_id,
        channel_code=req.channel_code.strip(),
        post=pdata,
    )
    return {"post": pdata}


@router.get("/board")
def list_board(
    channel_code: str,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    from app.db.models import ConsultBoardPost

    channel = consult_service.get_channel_by_code(db, channel_code.strip())
    if not channel:
        raise HTTPException(404, "频道不存在或未上架")
    posts = list(
        db.scalars(
            select(ConsultBoardPost)
            .where(
                ConsultBoardPost.channel_id == channel.id,
                ConsultBoardPost.parent_user_id == user_id,
            )
            .order_by(ConsultBoardPost.id.desc())
            .limit(50)
        ).all()
    )
    return {"posts": [consult_service.board_to_dict(p) for p in posts]}


@router.get("/im/token")
def get_im_token(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """可选 OpenIM；主实时为 WebSocket。"""
    _ = db
    if not consult_service.im_configured():
        raise HTTPException(
            503,
            "OpenIM 未配置（可选）。实时请用 /api/parent/consult/ws",
        )
    import os

    from app.services.openim_client import (
        PLATFORM_WEB,
        get_openim_client,
        parent_im_user_id,
    )

    im_uid = parent_im_user_id(user_id)
    client = get_openim_client()
    try:
        client.ensure_user(im_uid, nickname=f"家长{user_id}")
        data = client.get_user_token(im_uid, platform_id=PLATFORM_WEB)
    except Exception as e:
        raise HTTPException(502, f"OpenIM 发 token 失败: {e}") from e
    return {
        "im_user_id": im_uid,
        "token": data.get("token"),
        "expire_time_seconds": data.get("expireTimeSeconds"),
        "api_addr": consult_service.load_consult_config().get("im_api_url"),
        "ws_addr": os.getenv("CONSULT_IM_WS_URL", ""),
    }


@router.post("/im/callback")
def im_callback(
    req: ImCallbackRequest,
    db: Session = Depends(get_db),
    x_consult_token: str | None = Header(None, alias="X-Consult-Callback-Token"),
):
    cfg = consult_service.load_consult_config()
    if not consult_service.im_configured():
        raise HTTPException(503, "OpenIM 未配置")
    expect = cfg.get("im_callback_token") or ""
    if expect and x_consult_token != expect:
        raise HTTPException(401, "callback token 无效")
    _ = (req, db)
    raise HTTPException(501, "OpenIM webhook 待对接")
