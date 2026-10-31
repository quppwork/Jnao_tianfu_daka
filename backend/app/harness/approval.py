"""受控写审批 — 确认前不执行。与 Guide writes 确认卡并行，不替代业务闸门。"""

from __future__ import annotations

import secrets
import time
from typing import Any

_PENDING: dict[str, dict[str, Any]] = {}
_TTL_S = 600.0


def issue(tool: str, args: dict[str, Any], *, profile: str) -> str:
    _gc()
    token = secrets.token_urlsafe(12)
    _PENDING[token] = {
        "tool": tool,
        "args": dict(args),
        "profile": profile,
        "exp": time.time() + _TTL_S,
    }
    return token


def peek(token: str) -> dict[str, Any] | None:
    _gc()
    row = _PENDING.get(token or "")
    if not row:
        return None
    return row


def consume(token: str) -> dict[str, Any] | None:
    row = peek(token)
    if not row:
        return None
    _PENDING.pop(token, None)
    return row


def _gc() -> None:
    now = time.time()
    dead = [k for k, v in _PENDING.items() if float(v.get("exp") or 0) < now]
    for k in dead:
        _PENDING.pop(k, None)
