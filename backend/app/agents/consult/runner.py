"""在线咨询 Agent 核（Agent 层）— Role/Goal/出话编排。

按家长隔离的多轮记忆 + RAG(retrieve) + harness run_profile_turn。
轻量 ReAct：Thought → Action:retrieve → Observation → Answer + 引导追问。
群聊只取「当前提问家长」线程，避免串台。

会话 CRUD / WS 在 services；HTTP/WS 在 api/consult.py。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ConsultChannel, ConsultConversation, ConsultMessage

logger = logging.getLogger("jnao.consult.agent")

_SAY = re.compile(r"(?im)^\s*(?:Say|回答|Reply)\s*[:：]\s*(.+?)\s*$")
_THOUGHT_BLOCK = re.compile(
    r"(?is)^\s*(?:Thought|思考)\s*[:：].*?(?=^\s*(?:Say|回答|Reply|如果你还想)\s*[:：]|\Z)",
    re.M,
)
_FOLLOWUP_MARKERS = ("如果你还想", "你可能还想", "还可以继续问", "想进一步了解")

def _persona_for(channel: ConsultChannel) -> str:
    """人设/知识来自 harness LLM 路由层 PROFILES['consult']；meta.system_prompt 可整段覆盖。"""
    from app.harness.llm import profile_system

    meta = channel.meta_json or {}
    custom = (meta.get("system_prompt") or "").strip()
    code = (channel.bot_persona or channel.code or "dayu").strip()
    return profile_system("consult", persona=code, override=custom or None)


def _msg_for_parent(m: ConsultMessage, parent_user_id: int, parent_msg_ids: set[int]) -> bool:
    """判断该消息是否属于当前家长的对话线程。"""
    if m.sender_role == "parent":
        return int(m.sender_user_id or 0) == int(parent_user_id)
    if m.sender_role == "bot":
        meta = m.meta_json if isinstance(m.meta_json, dict) else {}
        if meta.get("kind") == "welcome":
            return False
        for_uid = meta.get("for_parent_id")
        if for_uid is not None:
            try:
                return int(for_uid) == int(parent_user_id)
            except (TypeError, ValueError):
                return False
        if m.reply_to_id and int(m.reply_to_id) in parent_msg_ids:
            return True
        # 历史无归属的 bot 气泡：不进入多用户群聊记忆，避免串台
        return False
    return False


def _history_for_parent(
    db: Session,
    conversation_id: int,
    parent_user_id: int,
    *,
    limit: int = 16,
) -> list[dict[str, str]]:
    """只取当前家长的多轮上下文（其发言 + 对其回复的 bot）。"""
    if parent_user_id < 1:
        return []
    rows = list(
        db.scalars(
            select(ConsultMessage)
            .where(
                ConsultMessage.conversation_id == conversation_id,
                ConsultMessage.visibility == "all",
            )
            .order_by(ConsultMessage.id.desc())
            .limit(120)
        ).all()
    )
    rows.reverse()
    parent_msg_ids: set[int] = set()
    out: list[dict[str, str]] = []
    for m in rows:
        if m.sender_role == "parent" and int(m.sender_user_id or 0) == int(parent_user_id):
            parent_msg_ids.add(int(m.id))
        if not _msg_for_parent(m, parent_user_id, parent_msg_ids):
            continue
        if m.sender_role == "parent":
            role = "user"
        elif m.sender_role == "bot":
            role = "assistant"
        else:
            continue
        content = (m.content or "").strip()
        if not content:
            continue
        # 过滤历史 stub 占位，避免污染模型上下文
        if role == "assistant" and (
            "（stub）" in content
            or "(stub)" in content.lower()
            or "请改用 DeepSeek Agent" in content
        ):
            continue
        out.append({"role": role, "content": content})
    if len(out) > limit:
        out = out[-limit:]
    # 末条若是刚写入的本轮用户消息，chat_completion 还会再 append，去掉以免重复
    if out and out[-1]["role"] == "user":
        out = out[:-1]
    return out


def _resolve_child_id(
    db: Session, conversation: ConsultConversation, parent_user_id: int
) -> int | None:
    """群聊 child 挂在会话上不可靠；优先用当前家长绑定的孩子。"""
    if parent_user_id > 0:
        try:
            from app.db.models import ParentChildBind

            cid = db.scalars(
                select(ParentChildBind.child_id)
                .where(ParentChildBind.parent_id == parent_user_id)
                .order_by(ParentChildBind.id.asc())
                .limit(1)
            ).first()
            if cid:
                return int(cid)
        except Exception:
            logger.exception("consult resolve child failed uid=%s", parent_user_id)
    if conversation.child_user_id:
        return int(conversation.child_user_id)
    return None


def _strip_react_scaffold(raw: str) -> str:
    """去掉 Thought/Action 脚手架，只留对用户可见的回答。"""
    text = (raw or "").strip()
    if not text:
        return ""
    says = _SAY.findall(text)
    if says:
        # Say 之后可能还有引导段，取 Say 行起至文末
        m = re.search(r"(?im)^\s*(?:Say|回答|Reply)\s*[:：]\s*", text)
        if m:
            rest = text[m.end() :].strip()
            # 若后面还有 Thought，截断
            cut = re.search(r"(?im)^\s*(?:Thought|思考|Action)\s*[:：]", rest)
            if cut:
                rest = rest[: cut.start()].strip()
            return rest
        return says[-1].strip()
    text = _THOUGHT_BLOCK.sub("", text).strip()
    text = re.sub(r"(?im)^\s*Action\s*[:：].*$", "", text).strip()
    text = re.sub(r"(?im)^\s*Observation\s*[:：].*$", "", text).strip()
    return text.strip()


def _ensure_followups(reply: str, user_text: str) -> str:
    """若模型未抛引导词，补一段「如果你还想了解」。"""
    t = (reply or "").strip()
    if not t:
        return t
    if any(m in t for m in _FOLLOWUP_MARKERS):
        return t
    # 根据当前问句给通用相关引导（不编造具体孩子数据）
    ask = (user_text or "").strip()
    hints: list[str] = []
    if any(k in ask for k in ("段位", "冲刺", "晋级", "升级")):
        hints = ["每日训练怎么坚持", "段位考核要注意什么", "孩子情绪不稳怎么沟通"]
    elif any(k in ask for k in ("不爱", "不想", "抗拒", "拖延", "训练")):
        hints = ["怎么把训练说成闯关", "家长焦虑怎么安抚", "今日训练入口在哪"]
    elif any(k in ask for k in ("沟通", "焦虑", "家长")):
        hints = ["孩子不听训练怎么办", "段位怎么冲刺", "如何看数据分析"]
    else:
        hints = ["段位怎么冲刺", "孩子不爱训练怎么办", "如何查看本周训练数据"]
    lines = "\n".join(f"- {h}" for h in hints[:3])
    return (
        f"{t}\n\n"
        f"如果你还想了解，可以继续 @大宇 问我：\n{lines}"
    )


def _react_system_extra() -> str:
    return (
        "【推理方式 · ReAct 轻量骨架】\n"
        "你可在内部按 Thought → Action → Observation 思考，但对用户输出时：\n"
        "1) 先给出正式回答（可用 Markdown 加粗、分点）；\n"
        "2) 回答末尾必须有一段引导：「如果你还想了解：」+ 2～3 条与本轮相关的追问方向"
        "（短句，不要编号成 chips，用列表即可）；\n"
        "3) 不要把 Thought/Action/Observation 原文暴露给用户；若你使用标记，"
        "请用「Say:」开头写对用户可见正文。\n"
        "4) 只根据【本家长对话记忆】与【知识库摘录】作答；"
        "禁止引用或臆测其他家长的发言、孩子或数据。\n"
        "5) 需要脑科学/五者天赋/因材施教知识时先 retrieve_kb"
        "（prefer_docs 可用 01-脑科学理论.md,02-五者天赋体系.md,03-因材施教指南.md），"
        "再根据工具结果回答；不要假装调用了查分/改档工具。"
    )


async def generate_consult_reply(
    db: Session,
    *,
    conversation: ConsultConversation,
    channel: ConsultChannel,
    user_text: str,
    parent_user_id: int = 0,
    trigger_msg_id: int | None = None,
    specialty_channels: list | None = None,
    group_room: bool = False,
) -> dict[str, Any]:
    """返回 {reply, intent, model, kb_hits, rag_used, error?}。

    群聊仅大宇应答；若 @ 了五者顾问，附带/改为「去单独咨询」引导。
    """
    from app.harness.context import ToolContext
    from app.harness.turn import run_profile_turn
    from app.services.consult_service import (
        build_dm_redirect_guide,
        parse_mentioned_bot_codes,
    )
    from app.services.doubao_client import is_configured

    del trigger_msg_id  # 预留给 job/审计
    text = (user_text or "").strip()
    if not text:
        return {
            "reply": "请先说一下你想咨询的问题～",
            "intent": "empty",
            "model": None,
            "kb_hits": [],
            "rag_used": False,
        }

    specialties = list(specialty_channels or [])
    mentioned = parse_mentioned_bot_codes(text)
    has_dayu = "dayu" in mentioned or text.strip().startswith("/ask")
    # 去掉 @ 词后是否还有实质问题
    ask_body = text
    for code in mentioned:
        from app.services.consult_service import mention_aliases_for

        for a in mention_aliases_for(code):
            ask_body = ask_body.replace("@" + a, " ")
            if a.isascii():
                ask_body = re.sub("@" + re.escape(a), " ", ask_body, flags=re.I)
    ask_body = re.sub(r"\s+", " ", ask_body).strip()
    redirect_only = bool(
        group_room and specialties and not has_dayu and len(ask_body) < 4
    )

    if redirect_only:
        guide = build_dm_redirect_guide(specialties)
        return {
            "reply": guide
            or "请点击上方对应顾问头像，进入单独咨询后再提问。",
            "intent": "redirect_dm",
            "model": None,
            "kb_hits": [],
            "rag_used": False,
            "for_parent_id": parent_user_id,
            "history_turns": 0,
        }

    child_block = ""
    child_id = _resolve_child_id(db, conversation, parent_user_id)
    if child_id:
        try:
            from app.agents.guide.context import build_guide_context

            gctx = build_guide_context(db, child_id)
            child_block = gctx.to_prompt_block()
        except Exception:
            logger.exception("consult child context failed")

    persona = _persona_for(channel)
    system_parts = [
        persona,
        _react_system_extra(),
        "回答使用简体中文，正文控制在 200～450 字内，可用少量 Markdown 加粗。"
        "需要课程/练法/政策知识时先 retrieve_kb；摘录不足时如实说明，不要编造政策/价格/名额。",
        f"【会话隔离】当前提问家长 user_id={parent_user_id}；"
        "下方记忆仅含该家长线程，勿与群内他人混淆。",
    ]
    if group_room:
        system_parts.append(
            "【群聊规则】本群只有你「大宇」直接作答。"
            "思者/赢者/德者/行者/学者顾问必须单独咨询，不能在群里冒充他们回答。"
            "若用户 @ 了这些顾问：先简要回应其问题（若有），再明确引导："
            "点击上方对应顾问头像进入单独咨询会话。"
        )
    if specialties:
        names = "、".join(ch.title for ch in specialties)
        system_parts.append(
            f"【用户想找的顾问】{names}\n"
            "请在回答末尾用简短段落引导家长点击顶部头像进入对应单独咨询；"
            "不要假装自己是这些顾问。"
        )
    if child_block:
        system_parts.append(f"【该家长关联孩子情境】\n{child_block}")

    system = "\n\n".join(system_parts)
    history = _history_for_parent(db, conversation.id, parent_user_id)
    from app.harness.memory import fold_and_truncate

    history, _ = fold_and_truncate(history, {}, keep=12)

    if not is_configured():
        logger.warning("consult DeepSeek not configured")
        fallback = (
            f"我是{channel.title}。对话模型未配置（DEEPSEEK_API_KEY），请稍后重试或联系管理员。"
        )
        if specialties:
            fallback = (fallback + "\n\n" + build_dm_redirect_guide(specialties)).strip()
        return {
            "reply": _ensure_followups(fallback, text) if not specialties else fallback,
            "intent": "no_llm",
            "model": None,
            "kb_hits": [],
            "rag_used": False,
            "error": "deepseek_not_configured",
        }

    try:
        hctx = ToolContext(
            db=db,
            parent_user_id=parent_user_id,
            child_user_id=int(child_id or 0),
            profile="consult",
        )
        turn = await run_profile_turn(
            "consult",
            text,
            history=history,
            ctx=hctx,
            system_override=system,
            max_steps=5,
        )
        reply = _strip_react_scaffold((turn.get("reply") or "").strip())
        rag_used = bool(turn.get("rag_used"))
        kb_hits = [
            t for t in (turn.get("tools_used") or []) if t.get("name") == "retrieve_kb"
        ]
    except Exception as e:
        logger.exception("consult harness failed")
        return {
            "reply": "刚才网络有点波动，请再发一次。若持续失败，可稍后再试。",
            "intent": "llm_error",
            "model": None,
            "kb_hits": [],
            "rag_used": False,
            "error": str(e)[:200],
        }

    if not reply:
        reply = "我这边暂时没整理出合适的答复，你可以换个问法，或继续 @大宇 再问一次。"
    if specialties:
        guide = build_dm_redirect_guide(specialties)
        if guide and "单独咨询" not in reply:
            reply = f"{reply}\n\n{guide}"
    else:
        reply = _ensure_followups(reply, text)

    from config.loader import load_settings

    model = (load_settings().get("deepseek") or {}).get("model") or "deepseek"
    return {
        "reply": reply,
        "intent": ("redirect_dm" if specialties else ("rag_llm" if rag_used else "llm")),
        "model": str(model),
        "kb_hits": kb_hits,
        "rag_used": rag_used,
        "for_parent_id": parent_user_id,
        "history_turns": len(history),
    }
