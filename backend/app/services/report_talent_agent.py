"""成人报告天赋解答 — LLM ReAct + talent_doc_retrieve 工具，按报告 ID 记忆。

会话落库只经 app.memory.ThreadStore（domain=report_talent）。
不绑学生/家长角色：只要能打开这份报告即可。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.harness.context import ToolContext
from app.harness.rag_contract import TALENT_DOC_SOURCE_KEY
from app.memory import ThreadRef, get_thread_store
from app.memory.protocols import DOMAIN_REPORT_TALENT, ThreadMessage
from app.model_cost import AgentFeature, get_cost_recorder
from app.services.report_talent_context import build_report_context
from app.services.report_talent_sections import (
    MAX_CITATIONS,
    REPORT_SECTIONS,
    derive_by_keywords,
)

OPENING = "您好我是你的天赋解答助手，有什么疑问都可以通过对话框向我提问，我会为您解答。"
REFUSAL = "抱歉我还不了解这部分内容，其他板块可能会有您需要的"

PROFILE = "report_talent"
# 工具轮默认 1 轮（查一次→直接出话）；max_steps 留出「查库 + 回答」两步余量
MAX_TOOL_ROUNDS = 1
MAX_STEPS = 4
HISTORY_LIMIT = 12
TOOL_NAME = "talent_doc_retrieve"

__all__ = [
    "OPENING",
    "REFUSAL",
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
    """从助手回复正文派生报告章节引用（保守：最多 MAX_CITATIONS 个）。

    RAG 命中带 citations 时以命中为准；本函数只做历史/兜底。
    """
    return derive_by_keywords(content, exclude=REFUSAL)


def _suggested_chips(talent: str) -> list[dict]:
    """报告专属情景问题，跟随该报告的主天赋。"""
    t = (talent or "").strip() or "这个天赋"
    return [
        {"q": f"{t}怎么练", "hot": True},
        {"q": "这份报告怎么看", "hot": True},
        {"q": f"{t}适合什么职业"},
        {"q": "五者是什么"},
    ]


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
        "chips": _suggested_chips(row.talent_primary),
        "messages": [_message_out(m) for m in rows],
    }


def _history_for_model(rows: list[ThreadMessage]) -> list[dict]:
    out: list[dict] = []
    for m in rows[-HISTORY_LIMIT:]:
        if m.role not in ("user", "assistant"):
            continue
        out.append({"role": m.role, "content": m.content})
    return out


def _inspect_tool_trace(trace: list[dict] | None) -> dict:
    """检查本轮工具：失败 / 空命中 / 成功。"""
    calls = [t for t in (trace or []) if t.get("name") == TOOL_NAME]
    if not calls:
        return {
            "called": False,
            "any_ok": False,
            "all_failed": False,
            "failures": [],
        }
    failures = [t for t in calls if not t.get("ok")]
    return {
        "called": True,
        "any_ok": any(t.get("ok") for t in calls),
        "all_failed": len(failures) == len(calls),
        "failures": [
            {"error": t.get("error"), "duration_ms": t.get("duration_ms")}
            for t in failures
        ],
    }


def _finalize_reply(raw: str, tool_info: dict) -> tuple[str, int, bool]:
    """门面只校验工具结果，不替模型做意图拦截。

    - 未调工具：采信模型直接回复（问候 / 引导提问等感知内能力）
    - 调了且有成功命中：采信模型回复，标记 retrieved
    - 调了但全失败 / 无命中：强制拒答口径
    """
    text = (raw or "").strip()
    if not tool_info["called"]:
        if text:
            return text, 0, False
        return REFUSAL, 0, True
    if tool_info["any_ok"] and text:
        return text, 1, False
    return REFUSAL, 0, True


def _clean_question(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise ReportTalentError("请输入问题", 400)
    if len(text) > 2000:
        raise ReportTalentError("问题过长", 400)
    return text


def _system_extra(row: TalentAssessment) -> str:
    """报告身份 + 报告正文切片：分数/五维以切片为准，不给「还没拿到数据」留口子。"""
    talent = (row.talent_primary or "").strip()
    parts = [
        f"当前报告 ID={row.id}。",
        f"报告主天赋标注为「{talent or '未标明'}」（仅作指代，不是库外事实）。",
    ]
    slice_text = build_report_context(
        row.report_json if isinstance(row.report_json, dict) else None, talent
    )
    if slice_text:
        parts.append("【报告正文切片 · 本报告唯一事实来源】\n" + slice_text)
        parts.append(
            "切片里已有的分数、五维、状态、天赋解读可直接引用；切片没有的数字不要编。"
        )
    else:
        parts.append("本报告暂无可用正文切片；不要编造分数、五维数值或职业清单。")
    return "".join(parts)


def _tool_context(db: Session, row: TalentAssessment) -> ToolContext:
    return ToolContext(
        db=db,
        actor_user_id=row.child_user_id,
        child_user_id=row.child_user_id,
        profile=PROFILE,
        extra={"assessment_id": row.id},
    )


def _turn_meta(row: TalentAssessment) -> dict[str, Any]:
    return {
        "assessment_id": row.id,
        "feature": AgentFeature.REPORT_TALENT,
    }


def _begin(db: Session, row: TalentAssessment, text: str):
    """用户句先落库（未 commit，等助手句一起提交）。"""
    store = get_thread_store(db)
    ref = _thread_ref(row)
    prior = store.list_messages(ref, limit=200)
    user = store.append(ref, role="user", content=text, commit=False)
    get_cost_recorder().bind_feature(AgentFeature.REPORT_TALENT)
    return store, ref, prior, user


def _resolve_reply(turn: dict[str, Any]) -> tuple[str, int, bool, dict]:
    """门面只校验工具结果，不替模型做意图拦截。"""
    tool_info = _inspect_tool_trace(turn.get("tools_used"))
    if tool_info["called"] and tool_info["all_failed"]:
        return REFUSAL, 0, True, tool_info
    reply, retrieved, refused = _finalize_reply(str(turn.get("reply") or ""), tool_info)
    return reply, retrieved, refused, tool_info


def _citations_for(turn: dict[str, Any], reply: str, refused: bool) -> list[str]:
    """优先用 RAG 命中章节；老路径 / 未带 citations 时退回正文关键词。"""
    if refused:
        return []
    raw = turn.get("citations")
    if isinstance(raw, list):
        cites = [str(c).strip() for c in raw if str(c).strip()]
        if cites:
            return cites[:MAX_CITATIONS]
    return _derive_citations(reply)


def _payload(
    user: ThreadMessage,
    assistant: ThreadMessage,
    turn: dict[str, Any],
    refused: bool,
    tool_info: dict,
) -> dict:
    return {
        "user": _message_out(user),
        "assistant": _message_out(assistant),
        "refused": refused,
        "tools_used": turn.get("tools_used") or [],
        "tool_check": tool_info,
        "llm_calls": turn.get("llm_calls") or 0,
        "rag_used": bool(turn.get("rag_used")),
        "profile": PROFILE,
    }


async def ask(db: Session, row: TalentAssessment, content: str) -> dict:
    _require_adult(row)
    text = _clean_question(content)
    store, ref, prior, user = _begin(db, row, text)

    from app.runtime import run_turn as run_profile_turn

    try:
        turn = await run_profile_turn(
            PROFILE,
            text,
            history=_history_for_model(prior),
            ctx=_tool_context(db, row),
            system_extra=_system_extra(row),
            max_steps=MAX_STEPS,
            max_tool_rounds=MAX_TOOL_ROUNDS,
            thread_id=f"report-talent-{row.id}",
            allow_tools=True,
            metadata=_turn_meta(row),
        )
    except Exception as e:
        db.rollback()
        raise ReportTalentError(f"助手暂时无法作答：{type(e).__name__}", 503) from e

    turn = turn if isinstance(turn, dict) else {}
    reply, retrieved, refused, tool_info = _resolve_reply(turn)
    citations = _citations_for(turn, reply, refused)

    assistant = store.append(
        ref,
        role="assistant",
        content=reply,
        meta={"retrieved": retrieved, "citations": citations},
        commit=True,
    )
    return _payload(user, assistant, turn, refused, tool_info)


async def ask_stream(
    db: Session, row: TalentAssessment, content: str
) -> AsyncIterator[tuple[str, Any]]:
    """SSE 版：先查一次库，最终答复真流式；done 里带落库后的权威消息。

    token  —— 增量正文（前端先渲染）
    replace —— 判为拒答时整段替换成统一口径
    error  —— 本轮失败（不落库助手句）
    done   —— {user, assistant, refused, citations, ...}，以这里为准
    """
    _require_adult(row)
    text = _clean_question(content)
    store, ref, prior, user = _begin(db, row, text)

    from app.runtime import run_turn_stream

    parts: list[str] = []
    done_turn: dict[str, Any] | None = None

    try:
        async for kind, payload in run_turn_stream(
            PROFILE,
            text,
            history=_history_for_model(prior),
            ctx=_tool_context(db, row),
            system_extra=_system_extra(row),
            max_steps=MAX_STEPS,
            max_tool_rounds=MAX_TOOL_ROUNDS,
            thread_id=f"report-talent-{row.id}",
            allow_tools=True,
            metadata=_turn_meta(row),
        ):
            if kind == "token":
                piece = str(payload or "")
                if piece.startswith("[ERROR]"):
                    db.rollback()
                    yield ("error", piece)
                    return
                parts.append(piece)
                yield ("token", piece)
            elif kind == "error":
                db.rollback()
                yield ("error", payload)
                return
            elif kind == "done" and isinstance(payload, dict):
                done_turn = payload
    except Exception as e:
        db.rollback()
        yield ("error", f"助手暂时无法作答：{type(e).__name__}")
        return

    turn = dict(done_turn or {})
    streamed = "".join(parts).strip()
    if streamed and not str(turn.get("reply") or "").strip():
        turn["reply"] = streamed

    reply, retrieved, refused, tool_info = _resolve_reply(turn)
    citations = _citations_for(turn, reply, refused)
    if refused and streamed and streamed != reply:
        yield ("replace", reply)

    assistant = store.append(
        ref,
        role="assistant",
        content=reply,
        meta={"retrieved": retrieved, "citations": citations},
        commit=True,
    )
    yield ("done", _payload(user, assistant, turn, refused, tool_info))

