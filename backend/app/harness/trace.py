"""一次工具调用的审计点：tool / duration / ok。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("jnao.harness.trace")

_EVENTS: list[dict[str, Any]] = []


def emit(
    tool: str,
    duration: int | float,
    ok: bool,
    *,
    profile: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    row = {
        "tool": tool,
        "duration": int(duration),
        "ok": bool(ok),
        "profile": profile or "",
        "error": (error or "")[:200] or None,
    }
    _EVENTS.append(row)
    if len(_EVENTS) > 200:
        del _EVENTS[:-100]
    logger.info(
        "trace tool=%s duration=%sms ok=%s profile=%s",
        tool,
        row["duration"],
        row["ok"],
        profile or "-",
    )
    return row


def recent(limit: int = 20) -> list[dict[str, Any]]:
    return list(_EVENTS[-max(1, limit) :])


def clear_for_tests() -> None:
    _EVENTS.clear()
