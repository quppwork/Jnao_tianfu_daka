"""在线咨询 — 配置 / IM 适配 / 会话业务；出话见 agents.consult.runner。"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    ConsultAgentJob,
    ConsultBoardPost,
    ConsultChannel,
    ConsultConversation,
    ConsultMember,
    ConsultMessage,
)


def load_consult_config() -> dict[str, Any]:
    """环境变量优先；未配齐 OpenIM 时推送 no-op，业务库仍可用。"""
    from app.services.openim_client import load_openim_config

    oi = load_openim_config()
    return {
        "im_provider": oi["provider"] or "openim",
        "im_api_url": oi["api_url"],
        "im_secret": oi["secret"],
        "im_admin_user": oi["admin_user"],
        "im_callback_token": oi["callback_token"],
        "im_bot_user_id": oi["bot_user_id"],
        "mq_url": (os.getenv("CONSULT_MQ_URL") or "").strip(),
        "agent_enabled": (os.getenv("CONSULT_AGENT_ENABLED", "1").strip() not in ("0", "false", "False")),
    }


def im_configured() -> bool:
    from app.services.openim_client import is_openim_ready

    return is_openim_ready()


# ── OpenIM 适配 ─────────────────────────────────────────────────────────────


class ImAdapter:
    """业务库 SoT → OpenIM 实时投递。密钥未配时全部跳过。"""

    def push_message(self, *, conversation: ConsultConversation, message: ConsultMessage) -> str | None:
        if not im_configured() or message.content_type != "text":
            return None
        from app.services.openim_client import (
            SESSION_GROUP,
            SESSION_SINGLE,
            get_openim_client,
            parent_im_user_id,
        )

        cfg = load_consult_config()
        client = get_openim_client()
        try:
            if conversation.kind == "group" and conversation.im_conversation_id:
                server_id = client.send_text(
                    send_id=cfg["im_bot_user_id"]
                    if message.sender_role == "bot"
                    else parent_im_user_id(message.sender_user_id or 0),
                    text=message.content,
                    group_id=conversation.im_conversation_id,
                    session_type=SESSION_GROUP,
                )
            else:
                # 单聊：bot → 家长
                recv = parent_im_user_id(conversation.parent_user_id)
                send = cfg["im_bot_user_id"]
                if message.sender_role == "parent":
                    # 家长消息一般由客户端 SDK 直发；服务端落库后可不重复推
                    return None
                server_id = client.send_text(
                    send_id=send,
                    text=message.content,
                    recv_id=recv,
                    session_type=SESSION_SINGLE,
                )
            if server_id and not message.im_msg_id:
                message.im_msg_id = server_id
            return server_id
        except Exception:
            # 推送失败不回滚业务消息；可后续重放
            import logging

            logging.getLogger("jnao.consult").exception(
                "OpenIM push failed conv=%s msg=%s", conversation.id, message.id
            )
            return None

    def ensure_conversation(self, conversation: ConsultConversation) -> str | None:
        if not im_configured():
            return None
        from app.services.openim_client import (
            dm_conversation_id,
            get_openim_client,
            parent_im_user_id,
        )

        cfg = load_consult_config()
        client = get_openim_client()
        parent_im = parent_im_user_id(conversation.parent_user_id)
        bot = cfg["im_bot_user_id"]
        try:
            client.ensure_user(parent_im, nickname=f"家长{conversation.parent_user_id}")
            client.ensure_user(bot, nickname="大宇智能体")
            if conversation.kind == "group":
                # 大宇群：每家长一群（或日后改成共用大群 + 分群策略）
                gid = conversation.im_conversation_id or f"jnao_g_dayu_{conversation.parent_user_id}"
                return client.create_group(
                    group_id=gid,
                    group_name="天赋家长交流群",
                    owner_user_id=bot,
                    member_user_ids=[parent_im],
                )
            # DM：业务侧记录约定 ID；OpenIM 单聊无需建会话
            return dm_conversation_id(parent_im, bot)
        except Exception:
            import logging

            logging.getLogger("jnao.consult").exception(
                "OpenIM ensure_conversation failed conv=%s", conversation.id
            )
            return None


_im = ImAdapter()


# ── Agent 任务入队（出话由 api/consult → agents.consult.runner）──────────────


def enqueue_agent_job(
    db: Session,
    *,
    conversation_id: int,
    trigger_msg_id: int,
    process_inline: bool = False,
) -> ConsultAgentJob:
    key = f"msg:{trigger_msg_id}"
    existing = db.scalars(
        select(ConsultAgentJob).where(ConsultAgentJob.idempotency_key == key)
    ).first()
    if existing:
        return existing

    job = ConsultAgentJob(
        conversation_id=conversation_id,
        trigger_msg_id=trigger_msg_id,
        status="queued",
        idempotency_key=key,
    )
    db.add(job)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        existing = db.scalars(
            select(ConsultAgentJob).where(ConsultAgentJob.idempotency_key == key)
        ).first()
        if existing:
            return existing
        raise

    cfg = load_consult_config()
    if cfg["mq_url"]:
        # TODO: publish to MQ
        pass
    _ = process_inline  # 兼容旧调用方；内联出话已迁到 API → Agent runner
    return job


def append_bot_message(
    db: Session,
    *,
    conversation: ConsultConversation,
    content: str,
    meta: dict | None = None,
    client_msg_id: str | None = None,
    reply_to_id: int | None = None,
) -> ConsultMessage:
    bot_msg = ConsultMessage(
        conversation_id=conversation.id,
        client_msg_id=client_msg_id or f"bot-{uuid.uuid4().hex[:16]}",
        sender_role="bot",
        sender_user_id=None,
        content_type="text",
        content=content,
        meta_json=meta,
        reply_to_id=reply_to_id,
    )
    db.add(bot_msg)
    db.flush()
    conversation.last_msg_at = bot_msg.created_at or datetime.utcnow()
    conversation.last_msg_preview = _preview(content)
    conversation.unread_parent = (conversation.unread_parent or 0) + 1
    db.flush()
    _im.push_message(conversation=conversation, message=bot_msg)
    return bot_msg


def finish_agent_job(
    db: Session,
    job: ConsultAgentJob,
    *,
    result_msg_id: int,
    intent: str | None,
    model: str | None,
    kb_hits: list | dict | None,
    error: str | None = None,
) -> None:
    job.status = "done"
    job.intent = intent
    job.model = model
    job.kb_hits_json = kb_hits
    job.result_msg_id = result_msg_id
    job.error = error
    job.finished_at = datetime.utcnow()
    if not job.started_at:
        job.started_at = job.finished_at
    db.flush()


def process_agent_job(db: Session, job_id: int) -> ConsultAgentJob | None:
    """已废弃：不再写 stub 占位。正式路径见 consult_agent.generate_consult_reply。"""
    job = db.get(ConsultAgentJob, job_id)
    if not job or job.status in ("done", "cancelled"):
        return job
    job.status = "cancelled"
    job.intent = "harness_only"
    job.model = None
    job.error = "stub_disabled_use_consult_agent"
    job.finished_at = datetime.utcnow()
    if not job.started_at:
        job.started_at = job.finished_at
    db.flush()
    return job


# ── 业务读写 ────────────────────────────────────────────────────────────────


def _preview(text: str, n: int = 180) -> str:
    t = (text or "").strip().replace("\n", " ")
    return t[:n]


def list_channels(db: Session) -> list[ConsultChannel]:
    return list(
        db.scalars(
            select(ConsultChannel)
            .where(ConsultChannel.status == "active")
            .order_by(ConsultChannel.sort_order, ConsultChannel.id)
        ).all()
    )


def channel_to_dict(ch: ConsultChannel) -> dict[str, Any]:
    meta = ch.meta_json or {}
    aliases = mention_aliases_for(ch.code)
    # @ 展示名：优先短名（大宇 / 思者），避免太长
    mention_name = aliases[0] if aliases else (ch.title or ch.code)
    return {
        "id": ch.id,
        "code": ch.code,
        "kind": ch.kind,
        "title": ch.title,
        "bot_persona": ch.bot_persona,
        "ai_enabled": bool(ch.ai_enabled),
        "human_handoff": bool(ch.human_handoff),
        "advisor_user_id": ch.advisor_user_id,  # 待填
        "im_group_template": ch.im_group_template,  # 待填
        "tag": meta.get("tag") or "",
        "tp": meta.get("tp") or "",
        "skill": meta.get("skill") or "",
        "chips": meta.get("chips") or [],
        "welcome": meta.get("welcome") or "",
        "board_enabled": bool(meta.get("board_enabled")),
        "mention_name": mention_name,
        "mention_aliases": list(aliases),
        "meta": meta,
    }


def get_channel_by_code(db: Session, code: str) -> ConsultChannel | None:
    return db.scalars(
        select(ConsultChannel).where(
            ConsultChannel.code == code,
            ConsultChannel.status == "active",
        )
    ).first()


def list_conversations(db: Session, parent_user_id: int) -> list[ConsultConversation]:
    """DM：自己发起的；群：自己作为成员的共享会话。"""
    dms = list(
        db.scalars(
            select(ConsultConversation).where(
                ConsultConversation.parent_user_id == parent_user_id,
                ConsultConversation.kind == "dm",
                ConsultConversation.status != "closed",
            )
        ).all()
    )
    member_conv_ids = list(
        db.scalars(
            select(ConsultMember.conversation_id).where(
                ConsultMember.user_id == parent_user_id,
                ConsultMember.role == "parent",
                ConsultMember.left_at.is_(None),
            )
        ).all()
    )
    groups: list[ConsultConversation] = []
    if member_conv_ids:
        groups = list(
            db.scalars(
                select(ConsultConversation).where(
                    ConsultConversation.id.in_(member_conv_ids),
                    ConsultConversation.kind == "group",
                    ConsultConversation.status != "closed",
                )
            ).all()
        )
    merged = {c.id: c for c in dms + groups}
    return sorted(
        merged.values(),
        key=lambda c: c.updated_at or c.created_at or datetime.min,
        reverse=True,
    )


def conversation_to_dict(
    conv: ConsultConversation,
    channel: ConsultChannel | None = None,
    *,
    db: Session | None = None,
) -> dict[str, Any]:
    member_count = 0
    if db is not None and conv.kind == "group":
        member_count = count_parent_members(db, conv.id)
    return {
        "id": conv.id,
        "channel_id": conv.channel_id,
        "channel_code": channel.code if channel else None,
        "channel_title": channel.title if channel else None,
        "kind": conv.kind,
        "status": conv.status,
        "child_user_id": conv.child_user_id,
        "assignee_id": conv.assignee_id,
        "im_conversation_id": conv.im_conversation_id,
        "last_msg_at": conv.last_msg_at.isoformat() if conv.last_msg_at else None,
        "last_msg_preview": conv.last_msg_preview,
        "unread_parent": conv.unread_parent or 0,
        "member_count": member_count,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


def parent_display_name(db: Session, user_id: int) -> str:
    from app.db.models import ChildUser

    if user_id < 1:
        return "家长"
    user = db.get(ChildUser, user_id)
    if not user:
        return f"家长{user_id}"
    pj = user.profile_json if isinstance(user.profile_json, dict) else {}
    name = (
        (pj.get("real_name") or "").strip()
        or (user.nickname or "").strip()
        or f"家长{user_id}"
    )
    return name


def count_parent_members(db: Session, conversation_id: int) -> int:
    from sqlalchemy import func

    return int(
        db.scalar(
            select(func.count())
            .select_from(ConsultMember)
            .where(
                ConsultMember.conversation_id == conversation_id,
                ConsultMember.role == "parent",
                ConsultMember.left_at.is_(None),
            )
        )
        or 0
    )


def list_parent_member_ids(db: Session, conversation_id: int) -> list[int]:
    return [
        int(uid)
        for uid in db.scalars(
            select(ConsultMember.user_id).where(
                ConsultMember.conversation_id == conversation_id,
                ConsultMember.role == "parent",
                ConsultMember.left_at.is_(None),
                ConsultMember.user_id > 0,
            )
        ).all()
    ]


def ensure_parent_member(db: Session, conversation_id: int, parent_user_id: int) -> None:
    existing = db.scalars(
        select(ConsultMember).where(
            ConsultMember.conversation_id == conversation_id,
            ConsultMember.user_id == parent_user_id,
            ConsultMember.role == "parent",
        )
    ).first()
    if existing:
        if existing.left_at is not None:
            existing.left_at = None
            db.flush()
        return
    db.add(
        ConsultMember(
            conversation_id=conversation_id,
            user_id=parent_user_id,
            role="parent",
        )
    )
    db.flush()


def open_conversation(
    db: Session,
    *,
    parent_user_id: int,
    channel_code: str,
    child_user_id: int | None = None,
) -> tuple[ConsultConversation, ConsultChannel, bool]:
    """群频道 = 全站共享一间；DM = 每家长一条。"""
    channel = get_channel_by_code(db, channel_code)
    if not channel:
        raise ValueError("频道不存在或未上架")

    if channel.kind == "group":
        conv = db.scalars(
            select(ConsultConversation).where(
                ConsultConversation.channel_id == channel.id,
                ConsultConversation.kind == "group",
                ConsultConversation.parent_user_id == 0,
                ConsultConversation.status != "closed",
            )
        ).first()
        created = False
        if not conv:
            conv = ConsultConversation(
                channel_id=channel.id,
                parent_user_id=0,
                child_user_id=None,
                kind="group",
                status="open",
                im_conversation_id=f"jnao_g_{channel.code}_shared",
            )
            db.add(conv)
            db.flush()
            db.add(
                ConsultMember(
                    conversation_id=conv.id,
                    user_id=0,
                    role="bot",
                )
            )
            welcome = (channel.meta_json or {}).get("welcome") or (
                f"欢迎来到{channel.title}。家长可在此交流；需要机器人时请输入 @ 选择，或长按头像 @。"
            )
            db.add(
                ConsultMessage(
                    conversation_id=conv.id,
                    client_msg_id=f"welcome-{channel.code}",
                    sender_role="bot",
                    content_type="text",
                    content=welcome,
                    meta_json={"kind": "welcome"},
                )
            )
            conv.last_msg_at = datetime.utcnow()
            conv.last_msg_preview = _preview(welcome)
            db.flush()
            created = True

        ensure_parent_member(db, conv.id, parent_user_id)
        return conv, channel, created

    existing = db.scalars(
        select(ConsultConversation).where(
            ConsultConversation.channel_id == channel.id,
            ConsultConversation.parent_user_id == parent_user_id,
            ConsultConversation.kind == "dm",
            ConsultConversation.status != "closed",
        )
    ).first()
    if existing:
        if child_user_id and existing.child_user_id != child_user_id:
            existing.child_user_id = child_user_id
            db.flush()
        ensure_parent_member(db, existing.id, parent_user_id)
        return existing, channel, False

    conv = ConsultConversation(
        channel_id=channel.id,
        parent_user_id=parent_user_id,
        child_user_id=child_user_id,
        kind="dm",
        status="open",
    )
    db.add(conv)
    db.flush()

    db.add(
        ConsultMember(
            conversation_id=conv.id,
            user_id=parent_user_id,
            role="parent",
        )
    )
    db.add(
        ConsultMember(
            conversation_id=conv.id,
            user_id=0,
            role="bot",
        )
    )
    if channel.advisor_user_id:
        db.add(
            ConsultMember(
                conversation_id=conv.id,
                user_id=channel.advisor_user_id,
                role="advisor",
            )
        )
    db.flush()

    im_id = _im.ensure_conversation(conv)
    if im_id:
        conv.im_conversation_id = im_id
        db.flush()

    welcome = (channel.meta_json or {}).get("welcome") or ""
    if welcome:
        db.add(
            ConsultMessage(
                conversation_id=conv.id,
                client_msg_id=f"welcome-{conv.id}",
                sender_role="bot",
                content_type="text",
                content=welcome,
                meta_json={"kind": "welcome"},
            )
        )
        conv.last_msg_at = datetime.utcnow()
        conv.last_msg_preview = _preview(welcome)
        db.flush()

    return conv, channel, True


def list_messages(
    db: Session,
    *,
    conversation_id: int,
    after_id: int | None = None,
    limit: int = 50,
) -> list[ConsultMessage]:
    q = select(ConsultMessage).where(
        ConsultMessage.conversation_id == conversation_id,
        ConsultMessage.visibility == "all",
    )
    if after_id:
        q = q.where(ConsultMessage.id > after_id)
    q = q.order_by(ConsultMessage.id.asc()).limit(min(limit, 200))
    return list(db.scalars(q).all())


def message_to_dict(
    m: ConsultMessage,
    *,
    viewer_user_id: int | None = None,
    channel: ConsultChannel | None = None,
    db: Session | None = None,
    name_cache: dict[int, str] | None = None,
) -> dict[str, Any]:
    is_me = bool(
        viewer_user_id
        and m.sender_role == "parent"
        and m.sender_user_id == viewer_user_id
    )
    sender_name = ""
    if m.sender_role == "parent":
        if is_me:
            sender_name = "我"
        elif db is not None and m.sender_user_id:
            cache = name_cache if name_cache is not None else {}
            uid = int(m.sender_user_id)
            if uid not in cache:
                cache[uid] = parent_display_name(db, uid)
            sender_name = cache[uid]
        else:
            sender_name = f"家长{m.sender_user_id or ''}"
    elif m.sender_role == "bot":
        meta = m.meta_json if isinstance(m.meta_json, dict) else {}
        sender_name = (
            (meta.get("persona_title") or "").strip()
            or (channel.title if channel else None)
            or "大宇智能体"
        )
    elif m.sender_role == "advisor":
        if db is not None and m.sender_user_id:
            sender_name = parent_display_name(db, m.sender_user_id)
        else:
            sender_name = "导师"
    else:
        sender_name = "系统"

    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "client_msg_id": m.client_msg_id,
        "im_msg_id": m.im_msg_id,
        "sender_role": m.sender_role,
        "sender_user_id": m.sender_user_id,
        "sender_name": sender_name,
        "is_me": is_me,
        "content_type": m.content_type,
        "content": m.content,
        "meta": m.meta_json,
        "reply_to_id": m.reply_to_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def send_parent_message(
    db: Session,
    *,
    conversation: ConsultConversation,
    parent_user_id: int,
    content: str,
    client_msg_id: str | None = None,
    content_type: str = "text",
    run_agent: bool = False,
) -> tuple[ConsultMessage, ConsultMessage | None]:
    """家长发消息 → SoT。默认不在此同步跑 Agent（由 API async + consult_agent）。"""
    cid = client_msg_id or f"c-{uuid.uuid4().hex[:20]}"
    existing = db.scalars(
        select(ConsultMessage).where(
            ConsultMessage.conversation_id == conversation.id,
            ConsultMessage.client_msg_id == cid,
        )
    ).first()
    if existing:
        bot = None
        job = db.scalars(
            select(ConsultAgentJob).where(
                ConsultAgentJob.trigger_msg_id == existing.id,
                ConsultAgentJob.status == "done",
            )
        ).first()
        if job and job.result_msg_id:
            bot = db.get(ConsultMessage, job.result_msg_id)
        return existing, bot

    msg = ConsultMessage(
        conversation_id=conversation.id,
        client_msg_id=cid,
        sender_role="parent",
        sender_user_id=parent_user_id,
        content_type=content_type or "text",
        content=content.strip(),
    )
    db.add(msg)
    db.flush()

    conversation.last_msg_at = msg.created_at or datetime.utcnow()
    conversation.last_msg_preview = _preview(msg.content)
    conversation.unread_advisor = (conversation.unread_advisor or 0) + 1
    db.flush()

    _im.push_message(conversation=conversation, message=msg)

    bot_msg: ConsultMessage | None = None
    channel = db.get(ConsultChannel, conversation.channel_id)
    if channel and channel.ai_enabled:
        job = enqueue_agent_job(
            db,
            conversation_id=conversation.id,
            trigger_msg_id=msg.id,
            process_inline=run_agent,
        )
        if run_agent and job.result_msg_id:
            bot_msg = db.get(ConsultMessage, job.result_msg_id)

    return msg, bot_msg


def create_board_post(
    db: Session,
    *,
    parent_user_id: int,
    channel_code: str,
    body: str,
    conversation_id: int | None = None,
) -> ConsultBoardPost:
    channel = get_channel_by_code(db, channel_code)
    if not channel:
        raise ValueError("频道不存在或未上架")
    post = ConsultBoardPost(
        channel_id=channel.id,
        parent_user_id=parent_user_id,
        conversation_id=conversation_id,
        body=body.strip(),
        status="open",
    )
    db.add(post)
    db.flush()
    return post


def board_to_dict(p: ConsultBoardPost) -> dict[str, Any]:
    return {
        "id": p.id,
        "channel_id": p.channel_id,
        "conversation_id": p.conversation_id,
        "body": p.body,
        "status": p.status,
        "reply_body": p.reply_body,
        "claimed_by": p.claimed_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def get_accessible_conversation(
    db: Session, *, conversation_id: int, parent_user_id: int
) -> ConsultConversation | None:
    conv = db.get(ConsultConversation, conversation_id)
    if not conv or conv.status == "closed":
        return None
    if conv.kind == "dm":
        return conv if conv.parent_user_id == parent_user_id else None
    mem = db.scalars(
        select(ConsultMember).where(
            ConsultMember.conversation_id == conversation_id,
            ConsultMember.user_id == parent_user_id,
            ConsultMember.role == "parent",
            ConsultMember.left_at.is_(None),
        )
    ).first()
    return conv if mem else None


def get_owned_conversation(
    db: Session, *, conversation_id: int, parent_user_id: int
) -> ConsultConversation | None:
    """兼容旧名 → 含群成员权限。"""
    return get_accessible_conversation(
        db, conversation_id=conversation_id, parent_user_id=parent_user_id
    )


# 群聊 @ 唤起：短名 / 全称均可
_BOT_MENTION_ALIASES: dict[str, tuple[str, ...]] = {
    "dayu": ("大宇", "大宇智能体", "dayu"),
    "sizhe": ("思者", "思者顾问"),
    "yingzhe": ("赢者", "赢者顾问"),
    "dezhe": ("德者", "德者顾问"),
    "xingzhe": ("行者", "行者顾问"),
    "xuezhe": ("学者", "学者顾问"),
}


def mention_aliases_for(code: str) -> tuple[str, ...]:
    return _BOT_MENTION_ALIASES.get((code or "").strip(), ())


def parse_mentioned_bot_codes(content: str) -> list[str]:
    """从正文解析被 @ 的机器人频道 code（按出现顺序，去重）。"""
    t = content or ""
    if "@" not in t and not t.strip().startswith("/ask"):
        return []
    found: list[str] = []
    low = t.lower()
    # 按别名长度降序，避免「大宇」抢在「大宇智能体」前误匹配后仍可再匹配长名
    pairs: list[tuple[str, str]] = []
    for code, aliases in _BOT_MENTION_ALIASES.items():
        for a in aliases:
            pairs.append((code, a))
    pairs.sort(key=lambda x: len(x[1]), reverse=True)
    for code, alias in pairs:
        needle = "@" + alias
        hit = needle.lower() in low if alias.isascii() else needle in t
        if hit and code not in found:
            found.append(code)
    if t.strip().startswith("/ask") and "dayu" not in found:
        found.insert(0, "dayu")
    return found


def should_auto_agent(channel: ConsultChannel, content: str) -> bool:
    """群聊：@任意机器人即由大宇应答（@其他顾问时引导去单独咨询）；私聊始终可 AI。"""
    if not channel.ai_enabled:
        return False
    if channel.kind != "group":
        return True
    return bool(parse_mentioned_bot_codes(content))


def mentioned_specialty_channels(
    db: Session, content: str
) -> list[ConsultChannel]:
    """群聊里 @ 到的非大宇顾问频道（需单独咨询）。"""
    out: list[ConsultChannel] = []
    for code in parse_mentioned_bot_codes(content):
        if code == "dayu":
            continue
        ch = get_channel_by_code(db, code)
        if ch:
            out.append(ch)
    return out


def build_dm_redirect_guide(channels: list[ConsultChannel]) -> str:
    """引导家长点顶部头像进入对应顾问私聊。"""
    if not channels:
        return ""
    lines: list[str] = []
    for ch in channels:
        skill = ""
        meta = ch.meta_json if isinstance(ch.meta_json, dict) else {}
        skill = (meta.get("skill") or "").strip()
        alias = mention_aliases_for(ch.code)
        short = alias[0] if alias else ch.title
        bit = f"**{ch.title}**"
        if skill:
            bit += f"（{skill}）"
        bit += f"：请点击上方「{short}」头像，进入**单独咨询**会话再提问。"
        lines.append(f"- {bit}")
    return (
        "五者顾问不在本群直接作答，需要单独咨询。\n\n"
        + "\n".join(lines)
        + "\n\n群里继续 @大宇，我可以帮你分流、解答通用问题。"
    )


def resolve_mentioned_channel(
    db: Session, *, group_channel: ConsultChannel, content: str
) -> ConsultChannel:
    """群聊统一由大宇应答；私聊返回当前频道。保留函数供兼容调用。"""
    del db, content
    return group_channel
