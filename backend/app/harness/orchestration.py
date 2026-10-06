"""编排面 — 不 spawn 子代理，不互调 runner。

复杂任务拆给另一个 Agent 的方式只有一种：handoff 包 → 前端跳转。
学院选角仍在 Scene Manager，不进本模块。
"""

from __future__ import annotations

from typing import Any

from app.agents.shared.handoff import (
    NAVIGATE_TARGETS,
    make_handoff_packet,
    resolve_reply_actions,
)

ORCHESTRATION_MODE = "handoff_packet"


def handoff_packet(
    *,
    intent: str,
    message: str,
    tools_used: list[dict[str, Any]] | None = None,
    child_id: int | None = None,
    image_id: str | int | None = None,
    from_agent: str = "guide",
) -> dict[str, str]:
    return make_handoff_packet(
        intent=intent,
        message=message,
        tools_used=tools_used,
        child_id=child_id,
        image_id=image_id,
        from_agent=from_agent,
    )


def navigate_actions(
    *,
    situation_next: str | None,
    message: str,
    child_id: int | None = None,
    has_assessment: bool = True,
) -> list[dict[str, Any]]:
    return resolve_reply_actions(
        situation_next=situation_next,
        message=message,
        child_id=child_id,
        has_assessment=has_assessment,
    )


__all__ = [
    "NAVIGATE_TARGETS",
    "ORCHESTRATION_MODE",
    "handoff_packet",
    "navigate_actions",
]
