"""成人报告天赋解答 — 优先调用 Agent 工具 knowledge_qa，原样返回。

会话落库只经 app.memory.ThreadStore（domain=report_talent）。
拒答 / 防注入由百炼知识问答应用配置；本门面不做二次改写。
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.harness.context import ToolContext
from app.harness.rag_contract import TALENT_DOC_SOURCE_KEY
from app.memory import ThreadRef, get_thread_store
from app.memory.protocols import DOMAIN_REPORT_TALENT, ThreadMessage
from app.model_cost import AgentFeature, get_cost_recorder
from app.services.report_talent_sections import (
    MAX_CITATIONS,
    REPORT_SECTIONS,
    derive_by_keywords,
)

OPENING = "您好我是你的天赋解答助手，有什么疑问都可以通过对话框向我提问，我会为您解答。"
# 仅工具调用失败（链路挂了）时的兜底；业务拒答以知识问答应用原文为准
TOOL_FAIL = "天赋解答暂时不可用，请稍后再试"

PROFILE = "report_talent"
MAX_TOOL_ROUNDS = 1
MAX_STEPS = 2
HISTORY_LIMIT = 12
TOOL_NAME = "knowledge_qa"

__all__ = [
    "OPENING",
    "TOOL_FAIL",
    "PROFILE",
    "MAX_TOOL_ROUNDS",
    "MAX_STEPS",
    "HISTORY_LIMIT",
    "TOOL_NAME",
    "REPORT_SECTIONS",
    "MAX_CITATIONS",
    "ReportTalentError",
    "ask",
    "ask_stream",
    "list_messages",
]


def _derive_citations(content: str) -> list[str]:
    return derive_by_keywords(content, exclude=TOOL_FAIL)


def _suggested_chips(
    talent: str,
    *,
    user_id: int | None = None,
    visit_key: str | None = None,
) -> list[dict]:
    """报告页 20 池轮换抽 4 条；与引导页池隔离。"""
    from app.suggest_prompts import report_suggest_chips

    return report_suggest_chips(
        talent,
        limit=4,
        user_id=user_id,
        visit_key=visit_key,
    )


class ReportTalentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


def _thread_ref(row: TalentAssessment) -> ThreadRef:
    return ThreadRef(
        domain=DOMAIN_REPORT_TALENT,
        owner_user_id=int(row.child_user_id),
        thread_key=str(row.id),
    )


def _message_out(msg: ThreadMessage) -> dict:
    meta = msg.meta or {}
    stored = meta.get("citations")
    if msg.role == "assistant":
        cites = (
            [str(c) for c in stored if str(c).strip()]
            if isinstance(stored, list)
            else _derive_citations(msg.content)
        )
    else:
        cites = []
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "retrieved": int(meta.get("retrieved") or 0),
        "citations": cites,
        "created_at": msg.created_at,
    }


def _require_adult(row: TalentAssessment) -> None:
    if int(row.test_type or 0) != 0:
        raise ReportTalentError("儿童报告不使用天赋解答助手", 403)


def list_messages(db: Session, row: TalentAssessment) -> dict:
    _require_adult(row)
    store = get_thread_store(db)
    rows = store.list_messages(_thread_ref(row), limit=500)
    return {
        "opening": OPENING,
        "assessment_id": row.id,
        "talent_primary": row.talent_primary or "",
        "test_type": int(row.test_type or 0),
        "source_key": TALENT_DOC_SOURCE_KEY,
        "chips": _suggested_chips(
            row.talent_primary or "",
            user_id=int(row.child_user_id),
            # visit_key 缺省 → 每次打开报告对话换一批
            visit_key=None,
        ),
        "messages": [_message_out(m) for m in rows],
    }


def _clean_question(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise ReportTalentError("请输入问题", 400)
    if len(text) > 2000:
        raise ReportTalentError("问题过长", 400)
    return text


_BOLD_SPACED = re.compile(r"\*\*\s*(.+?)\s*\*\*", re.DOTALL)


def _normalize_kb_reply(text: str) -> str:
    """百炼常见 `** “标题” **` → 标准 `**标题**`，方便前端加粗。"""
    t = (text or "").replace("\uFF0A", "*")
    return _BOLD_SPACED.sub(lambda m: f"**{m.group(1).strip()}**", t)


def _tool_context(db: Session, row: TalentAssessment) -> ToolContext:
    return ToolContext(
        db=db,
        actor_user_id=row.child_user_id,
        child_user_id=row.child_user_id,
        profile=PROFILE,
        extra={"assessment_id": row.id},
    )


def _compose_kb_query(row: TalentAssessment, user_text: str) -> str:
    """本份报告摘要 + 用户原问 → 交给 knowledge_qa（整份/局部由问句体现）。"""
    from app.services.report_talent_context import build_report_context

    report = row.report_json if isinstance(row.report_json, dict) else {}
    summary = build_report_context(report, getattr(row, "talent_primary", None))
    q = (user_text or "").strip()
    if not summary:
        return q
    return (
        "【本份测评报告摘要】\n"
        f"{summary}\n\n"
        "【用户问题】\n"
        f"{q}\n\n"
        "请结合报告摘要与知识库作答；报告里没有的分数/结论不要编造。"
    )


def _begin(db: Session, row: TalentAssessment, text: str):
    store = get_thread_store(db)
    ref = _thread_ref(row)
    prior = store.list_messages(ref, limit=200)
    user = store.append(ref, role="user", content=text, commit=False)
    get_cost_recorder().bind_feature(AgentFeature.REPORT_TALENT)
    return store, ref, prior, user


def _payload(
    user: ThreadMessage,
    assistant: ThreadMessage,
    *,
    tools_used: list[dict],
    tool_check: dict,
    refused: bool,
    llm_calls: int = 0,
) -> dict:
    return {
        "user": _message_out(user),
        "assistant": _message_out(assistant),
        "refused": refused,
        "tools_used": tools_used,
        "tool_check": tool_check,
        "llm_calls": llm_calls,
        "rag_used": bool(tool_check.get("any_ok")),
        "profile": PROFILE,
    }


def _audit_ok(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "ok": True,
        "aid": data.get("aid"),
        "request_id": data.get("request_id"),
    }


def _audit_fail(error: str | None = None, error_kind: str | None = None) -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "ok": False,
        "error": error,
        "error_kind": error_kind,
    }


async def ask(db: Session, row: TalentAssessment, content: str) -> dict:
    """优先 knowledge_qa；成功则原样落库返回，不再经本地 LLM 改写。"""
    _require_adult(row)
    text = _clean_question(content)
    store, ref, _prior, user = _begin(db, row, text)

    from app.harness.runtime import call_tool

    kb_query = _compose_kb_query(row, text)
    try:
        result = await call_tool(
            TOOL_NAME,
            {"query": kb_query},
            profile=PROFILE,
            ctx=_tool_context(db, row),
        )
    except Exception as e:
        db.rollback()
        raise ReportTalentError(f"助手暂时无法作答：{type(e).__name__}", 503) from e

    data = result.data if result.ok else {}
    reply = _normalize_kb_reply(str(data.get("reply") or "").strip())
    if result.ok and reply:
        tools_used = [_audit_ok(data)]
        tool_check = {"called": True, "any_ok": True, "all_failed": False, "failures": []}
        assistant = store.append(
            ref,
            role="assistant",
            content=reply,
            meta={"retrieved": 1, "citations": []},
            commit=True,
        )
        return _payload(
            user,
            assistant,
            tools_used=tools_used,
            tool_check=tool_check,
            refused=False,
        )

    # 链路失败：不替知识问答编业务拒答
    tools_used = [
        _audit_fail(
            error=result.error or data.get("error"),
            error_kind=data.get("error_kind"),
        )
    ]
    tool_check = {
        "called": True,
        "any_ok": False,
        "all_failed": True,
        "failures": [{"error": tools_used[0].get("error")}],
    }
    assistant = store.append(
        ref,
        role="assistant",
        content=TOOL_FAIL,
        meta={"retrieved": 0, "citations": []},
        commit=True,
    )
    return _payload(
        user,
        assistant,
        tools_used=tools_used,
        tool_check=tool_check,
        refused=True,
    )


async def ask_stream(
    db: Session, row: TalentAssessment, content: str
) -> AsyncIterator[tuple[str, Any]]:
    """SSE：知识问答流式 token 原样推送；done 带落库权威消息。"""
    _require_adult(row)
    text = _clean_question(content)
    store, ref, _prior, user = _begin(db, row, text)

    from app.services.bailian.config import load_bailian_config
    from app.services.bailian.knowledge_chat import knowledge_chat_stream
    from app.services.kb_policy import knowledge_qa_aid

    cfg = load_bailian_config()
    aid = knowledge_qa_aid()
    kb_query = _compose_kb_query(row, text)
    parts: list[str] = []
    final = None

    try:
        async for kind, payload in knowledge_chat_stream(
            kb_query, aid=aid, cfg=cfg, timeout=90
        ):
            if kind == "token":
                piece = str(payload or "")
                if piece:
                    parts.append(piece)
                    yield ("token", piece)
            elif kind == "result":
                final = payload
    except Exception as e:
        db.rollback()
        yield ("error", f"助手暂时无法作答：{type(e).__name__}")
        return

    reply = _normalize_kb_reply(
        str(getattr(final, "reply", "") or "").strip() or "".join(parts).strip()
    )
    if reply:
        tools_used = [
            _audit_ok(
                {
                    "aid": getattr(final, "aid", None) or aid,
                    "request_id": getattr(final, "request_id", None),
                }
            )
        ]
        tool_check = {"called": True, "any_ok": True, "all_failed": False, "failures": []}
        assistant = store.append(
            ref,
            role="assistant",
            content=reply,
            meta={"retrieved": 1, "citations": []},
            commit=True,
        )
        yield (
            "done",
            _payload(
                user,
                assistant,
                tools_used=tools_used,
                tool_check=tool_check,
                refused=False,
            ),
        )
        return

    if not parts:
        yield ("token", TOOL_FAIL)
    else:
        yield ("replace", TOOL_FAIL)
    tools_used = [_audit_fail(error="知识问答无回复", error_kind="empty")]
    tool_check = {
        "called": True,
        "any_ok": False,
        "all_failed": True,
        "failures": [{"error": "empty"}],
    }
    assistant = store.append(
        ref,
        role="assistant",
        content=TOOL_FAIL,
        meta={"retrieved": 0, "citations": []},
        commit=True,
    )
    yield (
        "done",
        _payload(
            user,
            assistant,
            tools_used=tools_used,
            tool_check=tool_check,
            refused=True,
        ),
    )
