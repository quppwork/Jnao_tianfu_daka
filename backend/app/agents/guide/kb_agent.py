"""引导页知识库 Agent — 豆包选源，百炼 Qwen 生成正文。"""

from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.context import GuideContext
from app.agents.guide.tools import call_tool, list_tools
from app.core.logger import get_logger
from app.services.kb_registry import KnowledgeSource, get_kb_registry

logger = get_logger("guide.kb_agent")

KB_FC_SYSTEM = (
    "你是首页引导的工具调度器，只负责选择知识源并调用工具，不要生成给用户的最终回答。"
    "可先 list_knowledge_sources，再必须调用 query_knowledge 查库。"
    "练法、怎么练、开口窍、超脑阅读、影像追忆、扫描速记、示范视频 → source_key=video_practice。"
    "其余知识问答默认 source_key=talent_doc："
    "天赋/五者/年级/晋级、平台说明、课程/产品/营期（如火箭提分营）、"
    "为什么要系统训练、什么是某某营/课 等。"
    "仅当用户在问今日训练进度、打招呼闲聊、或学科具体解题时，不要调用 query_knowledge。"
)

KB_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_knowledge_sources",
            "description": "列出可调用的百炼知识问答源（含 tags、summary、source_key）",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge",
            "description": "调用指定知识源问答，返回张宇老师口吻的正式回复（勿再改写）",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_key": {
                        "type": "string",
                        "description": "video_practice 或 talent_doc",
                    },
                    "query": {
                        "type": "string",
                        "description": "用户问题原文或略作补全的检索问句",
                    },
                },
                "required": ["source_key", "query"],
                "additionalProperties": False,
            },
        },
    },
]

_HOMEWORK_PATTERNS = (
    "这道题",
    "这题",
    "帮我做",
    "帮我算",
    "求解",
    "答案是",
    "怎么解这",
    "解一下",
    "作业题",
    "应用题",
    "计算题",
)

_PRACTICE_HINTS = (
    "怎么练",
    "如何练",
    "练法",
    "训练方法",
    "示范",
    "开口窍",
    "开口穹",
    "超脑",
    "影像追忆",
    "扫描速记",
    "极速运算",
    "极速学习",
    "多元感知",
)
_TALENT_HINTS = (
    "天赋",
    "学者",
    "思者",
    "赢者",
    "德者",
    "行者",
    "五者",
    "年级",
    "晋级",
)
_DOC_KNOWLEDGE_HINTS = (
    "什么是",
    "什么叫",
    "为什么",
    "介绍一下",
    "介绍下",
    "是什么",
    "提分营",
    "火箭",
    "营期",
    "课程",
    "产品",
    "收费",
    "多少钱",
    "适合谁",
    "系统训练",
    "单点刷题",
    "平台说明",
    "学习规律",
)
_SKIP_KB_HINTS = (
    "今日训练如何",
    "今日训练怎么样",
    "打卡情况",
    "练完了吗",
    "完成了吗",
    "你好",
    "您好",
    "在吗",
)


def _parse_kb_tool_calls(message: dict | None) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        return []
    raw_calls = message.get("tool_calls")
    if not isinstance(raw_calls, list):
        fc = message.get("function_call")
        if isinstance(fc, dict) and fc.get("name"):
            raw_calls = [{"type": "function", "function": fc}]
        else:
            return []
    allowed = {"list_knowledge_sources", "query_knowledge"}
    out: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") if isinstance(call.get("function"), dict) else call
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if name not in allowed:
            continue
        args_raw = fn.get("arguments", {})
        args: dict[str, Any] = {}
        if isinstance(args_raw, dict):
            args = args_raw
        elif isinstance(args_raw, str) and args_raw.strip():
            try:
                parsed = json.loads(args_raw)
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {}
        out.append({"name": str(name), "args": args})
    return out


def guide_kb_agent_enabled() -> bool:
    return (os.getenv("GUIDE_KB_AGENT") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def guide_kb_agent_ready() -> bool:
    if not guide_kb_agent_enabled():
        return False
    from app.services.bailian.config import load_bailian_config

    cfg = load_bailian_config()
    if not (cfg.workspace_id and cfg.dashscope_api_key):
        return False
    return len(get_kb_registry().sources) > 0


def is_homework_message(message: str) -> bool:
    from app.agents.shared.handoff import should_route_to_qa

    return should_route_to_qa(message)


def _looks_like_practice(message: str) -> bool:
    text = message or ""
    return any(h in text for h in _PRACTICE_HINTS)


def _looks_like_doc_knowledge(message: str) -> bool:
    text = message or ""
    if any(h in text for h in _TALENT_HINTS):
        return True
    if any(h in text for h in _DOC_KNOWLEDGE_HINTS):
        return True
    if ("什么" in text or "为何" in text or "为什么" in text) and not _looks_like_practice(text):
        return True
    return False


def _should_skip_kb_query(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return True
    return any(h in text for h in _SKIP_KB_HINTS)


def pick_source_by_tags(message: str) -> KnowledgeSource | None:
    """标签命中或启发式选库；非练法知识问默认 talent_doc。"""
    reg = get_kb_registry()
    text = (message or "").strip()
    if not text or _should_skip_kb_query(text):
        return None

    best: KnowledgeSource | None = None
    best_score = 0
    for src in reg.sources:
        score = sum(1 for tag in src.tags if tag and tag in text)
        if score > best_score:
            best_score = score
            best = src

    if best_score > 0:
        return best

    if _looks_like_practice(text):
        return reg.get("video_practice")
    if _looks_like_doc_knowledge(text):
        return reg.get("talent_doc")
    # 非练法：默认文档库（新入库主题未进 tags 时仍可查到）
    if not _looks_like_practice(text):
        return reg.get("talent_doc")
    return None


async def plan_kb_tool_calls(
    message: str,
    *,
    history: list[dict] | None = None,
) -> list[dict[str, Any]]:
    from app.services.doubao_client import chat_completion_message, is_configured

    text = (message or "").strip()
    if not text or _should_skip_kb_query(text) or is_homework_message(text):
        return []

    if not is_configured():
        src = pick_source_by_tags(text)
        if not src:
            return []
        return [{
            "name": "query_knowledge",
            "args": {"source_key": src.key, "query": text},
        }]

    list_tools()
    messages: list[dict[str, Any]] = [{"role": "system", "content": KB_FC_SYSTEM}]
    if history:
        for item in history[-4:]:
            role = item.get("role", "user")
            role = "assistant" if role in ("assistant", "ai", "bot") else "user"
            content = item.get("content") or item.get("text") or ""
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})

    try:
        msg = await chat_completion_message(
            messages=messages,
            tools=KB_TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=280,
            timeout=15,
        )
    except Exception as e:
        logger.warning("kb agent FC failed: %s", e)
        msg = None

    allowed = {"list_knowledge_sources", "query_knowledge"}
    picks: list[dict[str, Any]] = []
    for pick in _parse_kb_tool_calls(msg):
        if pick["name"] not in allowed:
            continue
        args = dict(pick.get("args") or {})
        if pick["name"] == "query_knowledge" and not args.get("query"):
            args["query"] = text
        picks.append({"name": pick["name"], "args": args})

    # 豆包只列源或漏调 query：按启发式补一次查库
    if not any(p["name"] == "query_knowledge" for p in picks):
        src = pick_source_by_tags(text)
        if src:
            picks.append({
                "name": "query_knowledge",
                "args": {"source_key": src.key, "query": text},
            })
    return picks


def _execute_kb_picks(
    db: Session,
    child_user_id: int,
    picks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    audit: list[dict[str, Any]] = []
    last_reply: str | None = None
    last_meta: dict[str, Any] | None = None

    for pick in picks:
        name = pick["name"]
        args = pick.get("args") or {}
        try:
            result = call_tool(db, child_user_id, name, args)
            ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
            audit.append({"name": name, "ok": ok, "args": args, "result": result})
            if name == "query_knowledge" and isinstance(result, dict) and result.get("ok"):
                last_reply = str(result.get("reply") or "").strip() or None
                last_meta = {
                    "source_key": result.get("source_key"),
                    "aid": result.get("aid"),
                    "request_id": result.get("request_id"),
                }
        except Exception as e:
            audit.append({"name": name, "ok": False, "args": args, "error": str(e)})

    return audit, last_reply, last_meta


async def run_guide_kb_turn(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    ctx: GuideContext | None = None,
) -> dict[str, Any] | None:
    """KB Agent 主入口。返回 None 表示交回普通对话兜底。"""
    if not guide_kb_agent_ready():
        return None

    text = (message or "").strip()
    if not text or len(text) < 2:
        return None

    if is_homework_message(text):
        from app.agents.shared.handoff import resolve_reply_actions, primary_navigate_target

        actions = resolve_reply_actions(
            situation_next=ctx.next_action if ctx else None,
            message=text,
            tools_used=[],
            has_assessment=bool(ctx.has_assessment) if ctx else False,
            reply="学科答疑",
        )
        qa_actions = [a for a in actions if a.get("type") == "navigate" and a.get("target") == "qa"]
        if not qa_actions:
            qa_actions = [{"type": "navigate", "target": "qa", "label": "去学科答疑 ›"}]
        return {
            "reply": "具体作业题去「学科答疑」里问更合适，我可以帮你在那边讲解思路～",
            "actions": qa_actions,
            "next_action": primary_navigate_target(qa_actions) or "qa",
            "situation": ctx.situation if ctx else None,
            "situation_label": None,
            "tools_used": [{"name": "kb_homework_redirect", "ok": True}],
            "rag_used": False,
            "rag_source": "homework_redirect",
        }

    picks = await plan_kb_tool_calls(text, history=history)
    audit, reply, kb_meta = _execute_kb_picks(db, child_user_id, picks)

    if not reply:
        src = pick_source_by_tags(text)
        if src:
            fallback_pick = {
                "name": "query_knowledge",
                "args": {"source_key": src.key, "query": text},
            }
            fb_audit, reply, kb_meta = _execute_kb_picks(
                db, child_user_id, [fallback_pick]
            )
            audit.extend(fb_audit)

    if not reply:
        logger.info("guide kb agent no reply uid=%s picks=%s", child_user_id, len(picks))
        return None

    from app.agents.guide.runner import _meta_from_ctx

    meta = _meta_from_ctx(ctx, message=text, tools_used=audit, reply=reply) if ctx else {}
    meta["rag_used"] = True
    meta["rag_source"] = "kb_qa_agent"
    if kb_meta:
        meta["kb_source_key"] = kb_meta.get("source_key")
        meta["kb_aid"] = kb_meta.get("aid")
        meta["kb_request_id"] = kb_meta.get("request_id")

    return {"reply": reply, **meta}


async def run_guide_kb_turn_stream_payload(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    ctx: GuideContext | None = None,
) -> dict[str, Any] | None:
    """流式：与 run_guide_kb_turn 相同，整段 reply 一次输出。"""
    return await run_guide_kb_turn(
        db, child_user_id, message, history=history, ctx=ctx
    )
