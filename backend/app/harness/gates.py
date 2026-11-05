"""内置 GateHook — 产品闸门逻辑仍在 facade 计算，经 metadata.product_gate 挂入循环前。

不做跨域超级编排：错科 / 「不会」引导等由 QA 门面判定后写入 product_gate，
内核只负责短接出话，避免再绕一套旁路 LLM。
"""

from __future__ import annotations

from app.harness.agent_state import AgentState
from app.harness.loop import register_gate

_INSTALLED = False


def _empty_user_gate(state: AgentState) -> AgentState | None:
    """空用户消息直接完成，避免无意义的模型调用。

    纯拍照答疑：用户气泡可为空，但消息里常有「题目识别预览」或 metadata.has_image。
    已挂 product_gate 时跳过，交给产品闸门短接。
    """
    meta = state.metadata or {}
    if isinstance(meta.get("product_gate"), dict) and meta["product_gate"].get("reply"):
        return None
    msgs = state.messages or []
    user = next((m for m in reversed(msgs) if m.get("role") == "user"), None)
    if user is None:
        return None
    content = str(user.get("content") or "").strip()
    if content:
        return None
    if meta.get("has_image") or meta.get("image_id"):
        return None
    state.status = "completed"
    state.reply = "请先说一下你的问题～"
    return state


def _product_gate(state: AgentState) -> AgentState | None:
    """门面预判的产品闸门：metadata.product_gate = {reply, code?, ...}。

    答疑错频道等硬约束由 facade 算好后写入 product_gate，此处只短接，不调模型。
    """
    meta = state.metadata or {}
    pg = meta.get("product_gate")
    if not isinstance(pg, dict):
        return None
    reply = str(pg.get("reply") or "").strip()
    if not reply:
        return None
    state.status = "completed"
    state.reply = reply
    meta["product_gate_hit"] = pg.get("code") or True
    # 答疑频道硬约束审计字段（可选）
    if pg.get("code") == "subject_mismatch":
        meta["qa_hard_constraint"] = "channel_mismatch"
    state.metadata = meta
    return state


def install_builtin_gates() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for profile in (
        "consult",
        "guide",
        "qa",
        "parent_guide",
        "academy",
        "harness",
        "report_talent",
    ):
        register_gate(profile, _empty_user_gate)
        register_gate(profile, _product_gate)
    _INSTALLED = True
