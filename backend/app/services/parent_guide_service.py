"""家长版大宇对话 — 知识库（课程/平台）+ 孩子训练/报告实况。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import GuideMessage, GuideSession
from app.services import guide_service, parent_service

PARENT_SESSION_TITLE = "家长助手"

PARENT_SYSTEM = """你是张宇老师的智能体「大宇」，面向家长对话。
结合「孩子情境」与工具结果，用简洁温暖的中文（3-6 句）回答。
可覆盖：孩子天赋报告解读、训练数据说明、家长课程/平台常识。
不要编造未给出的分数或打卡天数；没有数据时如实说明并引导去对应入口。
不要输出晋级公式或内部配置细节。"""

_LIVE_TRAIN_HINTS = (
    "训练数据",
    "打卡",
    "今日训练",
    "练完",
    "完成了吗",
    "进度",
    "连续",
    "段位",
    "能量",
    "修炼",
    "练得怎么样",
    "有没有练",
)
_LIVE_REPORT_HINTS = (
    "天赋报告",
    "测评报告",
    "报告结果",
    "报告解读",
    "看报告",
    "看下报告",
    "孩子的报告",
    "小孩报告",
    "什么天赋",
    "哪种天赋",
    "主导天赋",
    "是学者",
    "是思者",
    "是赢者",
    "是德者",
    "是行者",
)
_COURSE_HINTS = (
    "家长课程",
    "家长课堂",
    "72讲",
    "六门课",
    "6门课",
    "课程怎么",
    "怎么上课",
)
# 与进页 chips / 入库文档一致：概念问法走知识库，不要当成「孩子是哪种天赋」
_KB_TOPIC_HINTS = (
    "火箭提分营",
    "提分营",
    "超脑阅读",
    "开口窍",
    "开口穹",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "五者天赋",
    "学者天赋",
    "思者天赋",
    "行者天赋",
    "德者天赋",
    "赢者天赋",
)
_KB_CONCEPT_HINTS = (
    "怎么练",
    "怎么划分",
    "怎么分的",
    "适合谁",
    "怎么收费",
    "怎么解读",
    "服务周期",
)
_OWN_CHILD_HINTS = (
    "孩子",
    "小孩",
    "宝贝",
    "我家",
    "娃",
    "他",
    "她",
    "儿子",
    "女儿",
)


def resolve_focus_child_id(
    db: Session,
    parent_id: int,
    child_id: int | None = None,
) -> int:
    children = parent_service.list_children(db, parent_id)
    if not children:
        raise HTTPException(400, "请先绑定孩子训练账户")
    if child_id is not None:
        ids = {int(c["id"]) for c in children}
        if int(child_id) not in ids:
            raise HTTPException(403, "无权查看该孩子")
        return int(child_id)
    return int(children[0]["id"])


def match_child_from_message(
    message: str,
    children: list[dict],
) -> int | None:
    """从话术里匹配昵称；多命中或未命中返回 None。"""
    text = (message or "").strip()
    if not text or not children:
        return None
    hits: list[int] = []
    for c in children:
        nick = str(c.get("nickname") or "").strip()
        if nick and nick in text:
            hits.append(int(c["id"]))
    if len(hits) == 1:
        return hits[0]
    return None


def needs_child_clarification(
    message: str,
    children: list[dict],
    *,
    child_id: int | None,
) -> bool:
    """多孩且在问孩子数据、又未指定 child_id / 昵称时，先澄清。"""
    if len(children) <= 1:
        return False
    text = message or ""
    # 明确在问「哪个孩子」：即使已有 focus 也重新确认
    if any(k in text for k in ("哪个孩子", "先看哪个", "哪一个孩子", "切换孩子")):
        return True
    if child_id is not None:
        return False
    if match_child_from_message(message, children) is not None:
        return False
    if wants_platform_kb(message) and not asks_about_own_child(message):
        return False
    return wants_live_child_data(message)


def _clarify_child_reply(children: list[dict]) -> dict[str, Any]:
    names = [str(c.get("nickname") or "学员") for c in children[:6]]
    listed = "、".join(names)
    actions = []
    for c in children[:5]:
        cid = int(c["id"])
        nick = c.get("nickname") or "学员"
        actions.append({
            "type": "navigate",
            "target": "parent_pdata",
            "label": f"看{nick}的数据 ›",
            "path": f"/pages/parent/pdata?child_id={cid}",
            "child_id": cid,
        })
    return {
        "reply": (
            f"您绑定了多位孩子（{listed}）。想先看哪一位的报告或训练数据？"
            f"可以直接回复孩子昵称，或点下方按钮进入数据分析。"
        ),
        "actions": actions,
        "tools_used": [{"name": "clarify_child", "ok": True}],
        "rag_used": False,
        "rag_source": "parent_clarify_child",
        "focus_child_id": None,
        "situation": "multi_child",
        "next_action": "clarify_child",
    }


def wants_live_child_data(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if any(h in text for h in _LIVE_TRAIN_HINTS):
        return True
    if any(h in text for h in _LIVE_REPORT_HINTS):
        return True
    # 「报告」单独出现且提到孩子/查看，也按实况报告处理
    if "报告" in text and any(k in text for k in ("孩子", "小孩", "看", "查", "我")):
        return True
    return False


def wants_course_kb(message: str) -> bool:
    text = (message or "").strip()
    return any(h in text for h in _COURSE_HINTS)


def asks_about_own_child(message: str) -> bool:
    text = (message or "").strip()
    return any(h in text for h in _OWN_CHILD_HINTS)


def wants_platform_kb(message: str) -> bool:
    """平台/课程/五者等概念问 → 知识库（与 suggest chips 对齐）。"""
    text = (message or "").strip()
    if not text:
        return False
    if wants_course_kb(text):
        return True
    if any(h in text for h in _KB_TOPIC_HINTS):
        return True
    if any(h in text for h in _KB_CONCEPT_HINTS):
        return True
    # 「…是什么」「什么是…」释义问
    if text.startswith("什么是") or text.endswith("是什么") or "是什么？" in text:
        return True
    return False


def _get_or_create_parent_session(
    db: Session,
    parent_id: int,
    session_id: int | None = None,
) -> GuideSession:
    if session_id:
        session = db.get(GuideSession, session_id)
        if not session or session.child_user_id != parent_id:
            raise HTTPException(404, "会话不存在")
        return session
    session = guide_service.get_active_session(db, parent_id)
    if session:
        return session
    session = GuideSession(child_user_id=parent_id, title=PARENT_SESSION_TITLE)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _parent_actions(
    message: str,
    *,
    live: bool,
    kb: bool,
    child_id: int | None = None,
) -> list[dict[str, Any]]:
    text = message or ""
    actions: list[dict[str, Any]] = []
    pdata_path = (
        f"/pages/parent/pdata?child_id={child_id}"
        if child_id
        else "/pages/parent/pdata"
    )
    if live or any(h in text for h in _LIVE_TRAIN_HINTS) or "报告" in text:
        actions.append({
            "type": "navigate",
            "target": "parent_pdata",
            "label": "看数据分析 ›",
            "path": pdata_path,
            "child_id": child_id,
        })
    if any(h in text for h in _LIVE_REPORT_HINTS) or "天赋" in text:
        actions.append({
            "type": "navigate",
            "target": "talent_hub",
            "label": "去天赋测试 ›",
            "path": "/pages/talent/hub",
        })
    if kb or wants_course_kb(text):
        actions.append({
            "type": "navigate",
            "target": "parent_pcourse",
            "label": "进家长课堂 ›",
            "path": "/pages/parent/pcourse",
        })
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for a in actions:
        key = a.get("path") or a.get("target") or ""
        if key in seen:
            continue
        seen.add(str(key))
        out.append(a)
    return out[:3]


def _tool_block_from_results(rows: list[dict[str, Any]]) -> str:
    import json

    parts: list[str] = []
    for row in rows:
        name = row.get("name")
        result = row.get("result")
        if not row.get("ok"):
            parts.append(f"[{name}] 失败: {row.get('error') or result}")
            continue
        try:
            body = json.dumps(result, ensure_ascii=False)[:1200]
        except TypeError:
            body = str(result)[:1200]
        parts.append(f"[{name}] {body}")
    return "\n".join(parts)


async def _live_child_reply(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    from app.agents.guide.context import build_guide_context
    from app.agents.guide.tools import call_tool
    from app.services.doubao_client import chat_completion, is_configured

    ctx = build_guide_context(db, child_user_id)
    text = (message or "").strip()
    picks: list[tuple[str, dict]] = []
    if any(h in text for h in _LIVE_REPORT_HINTS) or "天赋" in text:
        picks.append(("get_talent_report_summary", {}))
    if any(h in text for h in _LIVE_TRAIN_HINTS) or not picks:
        picks.append(("get_today_plan", {}))
        picks.append(("get_checkin_timeline", {"limit": 7}))

    audit: list[dict[str, Any]] = []
    for name, args in picks:
        try:
            result = call_tool(db, child_user_id, name, args)
            ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
            audit.append({"name": name, "ok": ok, "args": args, "result": result})
        except Exception as e:  # noqa: BLE001
            audit.append({"name": name, "ok": False, "args": args, "error": str(e)})

    tool_block = _tool_block_from_results(audit)
    system = (
        f"{PARENT_SYSTEM}\n\n【孩子情境】\n{ctx.to_prompt_block()}\n\n"
        f"【工具结果】\n{tool_block or '（无）'}"
    )
    if not is_configured():
        reply = (
            f"已为你核对孩子「{ctx.nickname or '学员'}」的训练/报告数据。"
            "AI 暂未配置，请到「数据分析」查看明细。"
        )
    else:
        reply = await chat_completion(
            system_prompt=system,
            user_message=text,
            history=history or [],
            max_tokens=420,
        )
        reply = (reply or "").strip() or "我这边暂时没整理出结论，你可以先打开「数据分析」看一眼。"

    return {
        "reply": reply,
        "actions": _parent_actions(text, live=True, kb=False, child_id=child_user_id),
        "tools_used": audit,
        "rag_used": False,
        "rag_source": "parent_live_tools",
        "focus_child_id": child_user_id,
        "situation": ctx.situation,
        "next_action": "parent_pdata",
    }


async def _kb_or_minimal_reply(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    from app.agents.guide.context import build_guide_context
    from app.agents.guide.kb_agent import run_guide_kb_turn
    from app.services.doubao_client import chat_completion, is_configured

    ctx = build_guide_context(db, child_user_id)
    kb = await run_guide_kb_turn(
        db, child_user_id, message, history=history, ctx=ctx
    )
    if kb and (kb.get("reply") or "").strip():
        out = dict(kb)
        out["actions"] = _parent_actions(
            message, live=False, kb=True, child_id=child_user_id
        ) or out.get("actions") or []
        out["focus_child_id"] = child_user_id
        out.setdefault("rag_source", "kb_qa_agent")
        return out

    # 无库命中：用人设 + 孩子情境兜底，并引导课堂/咨询
    system = f"{PARENT_SYSTEM}\n\n【孩子情境】\n{ctx.to_prompt_block()}"
    if is_configured():
        reply = await chat_completion(
            system_prompt=system,
            user_message=message,
            history=history or [],
            max_tokens=360,
        )
        reply = (reply or "").strip()
    else:
        reply = ""
    if not reply:
        reply = (
            "家长您好。关于课程与平台说明，可进「家长课堂」；"
            "孩子训练与报告可问我「训练数据 / 天赋报告」，或点上方入口。"
        )
    return {
        "reply": reply,
        "actions": _parent_actions(message, live=False, kb=True, child_id=child_user_id),
        "tools_used": [],
        "rag_used": False,
        "rag_source": "parent_minimal",
        "focus_child_id": child_user_id,
        "situation": ctx.situation,
        "next_action": "parent_pcourse" if wants_course_kb(message) else None,
    }


async def run_parent_turn(
    db: Session,
    parent_id: int,
    message: str,
    *,
    child_id: int | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    from app.services.ai_output_guard import is_prompt_injection_attempt, refusal_message

    if is_prompt_injection_attempt(message):
        return {
            "reply": refusal_message(),
            "actions": [],
            "tools_used": [],
            "rag_used": False,
            "rag_source": "injection_refusal",
        }

    children = parent_service.list_children(db, parent_id)
    if not children:
        raise HTTPException(400, "请先绑定孩子训练账户")

    if needs_child_clarification(message, children, child_id=child_id):
        return _clarify_child_reply(children)

    matched = match_child_from_message(message, children)
    focus_child = resolve_focus_child_id(
        db, parent_id, child_id if child_id is not None else matched
    )
    # 概念/课程问优先走知识库；带「孩子/他」的实况问再走工具
    if wants_platform_kb(message) and not asks_about_own_child(message):
        return await _kb_or_minimal_reply(
            db, focus_child, message, history=history
        )
    if wants_live_child_data(message):
        return await _live_child_reply(
            db, focus_child, message, history=history
        )
    return await _kb_or_minimal_reply(
        db, focus_child, message, history=history
    )


def _history_for_llm(session: GuideSession) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in session.messages]


def _assistant_meta(result: dict) -> dict | None:
    actions = list(result.get("actions") or [])
    tools_used = list(result.get("tools_used") or [])
    blocks = list(result.get("blocks") or [])
    if not actions and not tools_used and not blocks:
        return None
    return {"actions": actions, "tools_used": tools_used, "blocks": blocks}


async def chat(
    db: Session,
    parent_id: int,
    message: str,
    *,
    session_id: int | None = None,
    child_id: int | None = None,
) -> dict[str, Any]:
    session = _get_or_create_parent_session(db, parent_id, session_id)
    history = _history_for_llm(session)

    db.add(GuideMessage(session_id=session.id, role="user", content=message))
    if not session.title or session.title == PARENT_SESSION_TITLE:
        session.title = (message or "")[:30] or PARENT_SESSION_TITLE
    db.commit()

    result = await run_parent_turn(
        db, parent_id, message, child_id=child_id, history=history
    )
    reply = result.get("reply") or ""
    db.add(
        GuideMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=_assistant_meta(result),
        )
    )
    db.commit()
    guide_service._archive_session_overflow(db, session)  # noqa: SLF001

    return {
        "session_id": session.id,
        "focus_child_id": result.get("focus_child_id"),
        "reply": reply,
        "actions": result.get("actions") or [],
        "tools_used": result.get("tools_used") or [],
        "rag_used": bool(result.get("rag_used")),
        "rag_source": result.get("rag_source"),
        "situation": result.get("situation"),
        "next_action": result.get("next_action"),
    }


async def chat_stream(
    db: Session,
    parent_id: int,
    message: str,
    *,
    session_id: int | None = None,
    child_id: int | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """流式：思考状态 → 整段回复（会话已持久化）。"""
    yield ("status", "agent思考中…")
    children = parent_service.list_children(db, parent_id)
    if needs_child_clarification(message, children, child_id=child_id):
        yield ("status", "发现多位孩子，正在确认…")
    elif wants_platform_kb(message) and not asks_about_own_child(message):
        yield ("status", "正在查询知识库…")
    elif wants_live_child_data(message):
        yield ("status", "正在查阅孩子训练与报告…")
    else:
        yield ("status", "正在查询知识库…")

    result = await chat(
        db,
        parent_id,
        message,
        session_id=session_id,
        child_id=child_id,
    )
    reply = result.get("reply") or ""
    if reply:
        yield ("token", reply)
    yield ("done", result)


def load_session_payload(db: Session, parent_id: int) -> dict:
    return guide_service.load_session_payload(db, parent_id)
