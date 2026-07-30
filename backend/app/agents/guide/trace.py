"""Guide 回合可观测（R9）— 工具链 / 耗时 / 空工具率。

结构化日志字段前缀 `guide_trace`，便于预发/线上 grep；进程内累计指标供 debug。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.core.logger import get_logger

logger = get_logger("guide.trace")

_lock = threading.Lock()
_METRICS: dict[str, float | int] = {
    "turns": 0,
    "empty_tools_turns": 0,
    "tool_calls": 0,
    "tool_ok": 0,
    "tool_fail": 0,
    "leak_flagged": 0,
    "total_ms": 0.0,
}


def reset_guide_trace_metrics() -> None:
    with _lock:
        for k in list(_METRICS):
            _METRICS[k] = 0 if k != "total_ms" else 0.0


def get_guide_trace_metrics() -> dict[str, Any]:
    with _lock:
        turns = int(_METRICS["turns"])
        empty = int(_METRICS["empty_tools_turns"])
        total_ms = float(_METRICS["total_ms"])
        return {
            "turns": turns,
            "empty_tools_turns": empty,
            "empty_tool_rate": (empty / turns) if turns else 0.0,
            "tool_calls": int(_METRICS["tool_calls"]),
            "tool_ok": int(_METRICS["tool_ok"]),
            "tool_fail": int(_METRICS["tool_fail"]),
            "leak_flagged": int(_METRICS["leak_flagged"]),
            "avg_ms": (total_ms / turns) if turns else 0.0,
        }


def build_turn_trace(
    *,
    child_user_id: int,
    message: str,
    tools_used: list[dict[str, Any]] | None,
    duration_ms: float,
    situation: str | None = None,
    next_action: str | None = None,
    reply: str | None = None,
    leak_hits: list[str] | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    tools = tools_used or []
    names = [str(t.get("name") or "") for t in tools if isinstance(t, dict)]
    ok_n = sum(1 for t in tools if isinstance(t, dict) and t.get("ok") is not False)
    fail_n = sum(1 for t in tools if isinstance(t, dict) and t.get("ok") is False)
    rounds = sorted({
        int(t.get("round") or 0)
        for t in tools
        if isinstance(t, dict) and t.get("round") is not None
    })
    return {
        "child_user_id": child_user_id,
        "message_len": len(message or ""),
        "message_preview": (message or "")[:40],
        "situation": situation,
        "next_action": next_action,
        "tool_names": names,
        "tool_count": len(tools),
        "tool_ok": ok_n,
        "tool_fail": fail_n,
        "empty_tools": len(tools) == 0,
        "rounds": rounds,
        "duration_ms": round(float(duration_ms), 1),
        "reply_len": len(reply or ""),
        "leak_hits": list(leak_hits or []),
        "stream": stream,
    }


def emit_guide_trace(trace: dict[str, Any]) -> None:
    """写结构化日志并更新进程内指标。"""
    with _lock:
        _METRICS["turns"] = int(_METRICS["turns"]) + 1
        if trace.get("empty_tools"):
            _METRICS["empty_tools_turns"] = int(_METRICS["empty_tools_turns"]) + 1
        _METRICS["tool_calls"] = int(_METRICS["tool_calls"]) + int(
            trace.get("tool_count") or 0
        )
        _METRICS["tool_ok"] = int(_METRICS["tool_ok"]) + int(trace.get("tool_ok") or 0)
        _METRICS["tool_fail"] = int(_METRICS["tool_fail"]) + int(
            trace.get("tool_fail") or 0
        )
        if trace.get("leak_hits"):
            _METRICS["leak_flagged"] = int(_METRICS["leak_flagged"]) + 1
        _METRICS["total_ms"] = float(_METRICS["total_ms"]) + float(
            trace.get("duration_ms") or 0
        )

    try:
        payload = json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        payload = str(trace)
    logger.info(f"guide_trace {payload}")


class TurnTimer:
    """简易耗时计时。"""

    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
