"""对外公开 turn 结果形状 — runtime / 旧 harness.turn 共用。"""

from __future__ import annotations

from typing import Any

from app.harness.agent_state import AgentState


def _trace_rag(trace: list[dict[str, Any]]) -> bool:
    names = {
        "retrieve_kb",
        "retrieve_qa_kb",
        "retrieve_qa_legacy",
        "talent_doc_retrieve",
    }
    return any(t.get("name") in names and t.get("ok") for t in (trace or []))


def public_turn(state: AgentState, profile: str) -> dict[str, Any]:
    meta = state.metadata or {}
    return {
        "reply": (state.reply or "").strip(),
        "status": state.status,
        "tools_used": list(state.tool_trace or []),
        "rag_used": _trace_rag(state.tool_trace),
        "citations": [str(c) for c in (meta.get("citations") or []) if str(c).strip()],
        "thread_id": state.thread_id,
        "pending_approvals": [p.to_dict() for p in state.pending_approvals],
        "profile": profile,
        "llm_calls": int(meta.get("llm_calls") or 0),
    }
