"""内置 GateHook — 产品闸门仍在 facade；此处只挂循环前的轻量内核闸门。"""

from __future__ import annotations

from app.harness.agent_state import AgentState
from app.harness.loop import register_gate

_INSTALLED = False


def _empty_user_gate(state: AgentState) -> AgentState | None:
    """空用户消息直接完成，避免无意义的模型调用。

    纯拍照答疑：用户气泡可为空，但消息里常有「题目识别预览」或 metadata.has_image。
    """
    msgs = state.messages or []
    user = next((m for m in reversed(msgs) if m.get("role") == "user"), None)
    if user is None:
        return None
    content = str(user.get("content") or "").strip()
    if content:
        return None
    meta = state.metadata or {}
    if meta.get("has_image") or meta.get("image_id"):
        return None
    state.status = "completed"
    state.reply = "请先说一下你的问题～"
    return state


def install_builtin_gates() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for profile in ("consult", "guide", "qa", "parent_guide", "academy", "harness"):
        register_gate(profile, _empty_user_gate)
    _INSTALLED = True
