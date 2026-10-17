"""成人报告天赋解答 — LLM ReAct + talent_doc_retrieve 工具，按报告 ID 记忆。

会话落库只经 app.memory.ThreadStore（domain=report_talent）。
不绑学生/家长角色：只要能打开这份报告即可。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.harness.context import ToolContext
from app.harness.rag_contract import TALENT_DOC_SOURCE_KEY
from app.memory import ThreadRef, get_thread_store
from app.memory.protocols import DOMAIN_REPORT_TALENT, ThreadMessage
from app.model_cost import AgentFeature, get_cost_recorder

OPENING = "您好我是你的天赋解答助手，有什么疑问都可以通过对话框向我提问，我会为您解答。"
REFUSAL = "抱歉我还不了解这部分内容，其他板块可能会有您需要的"

PROFILE = "report_talent"
MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 12
TOOL_NAME = "talent_doc_retrieve"

# 报告页章节锚点（与 report-v3.html 前端 .tintro/#abilList/#hallx/#theater 对齐）。
# citations 是 content 的纯函数：不持久化，历史消息读取时同样可派生。
REPORT_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("五维能量星图", ("执行力", "公信力", "协调力", "创新力", "领导力", "五维", "星图")),
    ("名人堂", ("名人堂", "榜样")),
    ("天赋剧场", ("剧场", "短片")),
)
MAX_CITATIONS = 2


def _derive_citations(content: str) -> list[str]:
    """从助手回复正文派生报告章节引用（保守：最多 MAX_CITATIONS 个）。"""
    text = (content or "").strip()
    if not text or text == REFUSAL:
        return []
    out: list[str] = []
    for label, keys in REPORT_SECTIONS:
        if any(k in text for k in keys):
            out.append(label)
        if len(out) >= MAX_CITATIONS:
            break
    return out


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
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "retrieved": int((msg.meta or {}).get("retrieved") or 0),
        "citations": _derive_citations(msg.content) if msg.role == "assistant" else [],
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


async def ask(db: Session, row: TalentAssessment, content: str) -> dict:
    _require_adult(row)
    text = (content or "").strip()
    if not text:
        raise ReportTalentError("请输入问题", 400)
    if len(text) > 2000:
        raise ReportTalentError("问题过长", 400)

    store = get_thread_store(db)
    ref = _thread_ref(row)
    prior = store.list_messages(ref, limit=200)

    # 用户句先落库（未 commit，等助手句一起提交）
    user = store.append(ref, role="user", content=text, commit=False)

    get_cost_recorder().bind_feature(AgentFeature.REPORT_TALENT)

    from app.runtime import run_turn as run_profile_turn

    talent = (row.talent_primary or "").strip()
    system_extra = (
        f"当前报告 ID={row.id}。"
        f"报告主天赋标注为「{talent or '未标明'}」（仅作指代，不是库外事实）。"
        "报告正文切片尚未联调，不要编造分数或职业清单。"
    )
    ctx = ToolContext(
        db=db,
        actor_user_id=row.child_user_id,
        child_user_id=row.child_user_id,
        profile=PROFILE,
        extra={"assessment_id": row.id},
    )

    try:
        turn = await run_profile_turn(
            PROFILE,
            text,
            history=_history_for_model(prior),
            ctx=ctx,
            system_extra=system_extra,
            max_steps=MAX_TOOL_ROUNDS,
            thread_id=f"report-talent-{row.id}",
            allow_tools=True,
            metadata={
                "assessment_id": row.id,
                "feature": AgentFeature.REPORT_TALENT,
            },
        )
    except Exception as e:
        db.rollback()
        raise ReportTalentError(f"助手暂时无法作答：{type(e).__name__}", 503) from e

    tool_info = _inspect_tool_trace(turn.get("tools_used"))
    if tool_info["called"] and tool_info["all_failed"]:
        reply, retrieved, refused = REFUSAL, 0, True
    else:
        reply, retrieved, refused = _finalize_reply(
            str(turn.get("reply") or ""), tool_info
        )

    assistant = store.append(
        ref,
        role="assistant",
        content=reply,
        meta={"retrieved": retrieved},
        commit=True,
    )

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
