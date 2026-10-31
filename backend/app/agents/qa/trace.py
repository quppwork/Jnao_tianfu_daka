"""QA 回合可观测 — 学科 / OCR / RAG / mismatch / 耗时。

结构化日志前缀 `qa_trace`；进程内累计指标供 debug。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.core.logger import get_logger

logger = get_logger("qa.trace")

_lock = threading.Lock()
_METRICS: dict[str, float | int] = {
    "turns": 0,
    "mismatch_turns": 0,
    "clarify_turns": 0,
    "ocr_turns": 0,
    "rag_turns": 0,
    "total_ms": 0.0,
}


def reset_qa_trace_metrics() -> None:
    with _lock:
        for k in list(_METRICS):
            _METRICS[k] = 0 if k != "total_ms" else 0.0


def get_qa_trace_metrics() -> dict[str, Any]:
    with _lock:
        turns = int(_METRICS["turns"])
        total_ms = float(_METRICS["total_ms"])
        return {
            "turns": turns,
            "mismatch_turns": int(_METRICS["mismatch_turns"]),
            "clarify_turns": int(_METRICS["clarify_turns"]),
            "ocr_turns": int(_METRICS["ocr_turns"]),
            "rag_turns": int(_METRICS["rag_turns"]),
            "avg_ms": (total_ms / turns) if turns else 0.0,
        }


def build_qa_turn_trace(
    *,
    child_user_id: int,
    session_id: int | None,
    subject: str | None,
    message: str,
    duration_ms: float,
    reply: str | None = None,
    has_image: bool = False,
    ocr_used: bool = False,
    rag_used: bool = False,
    subject_mismatch: bool = False,
    suggested_subject: str | None = None,
    clarified: bool = False,
    stream: bool = False,
    school_stage: str | None = None,
) -> dict[str, Any]:
    return {
        "child_user_id": child_user_id,
        "session_id": session_id,
        "subject": subject,
        "school_stage": school_stage,
        "message_len": len(message or ""),
        "message_preview": (message or "")[:40],
        "has_image": bool(has_image),
        "ocr_used": bool(ocr_used),
        "rag_used": bool(rag_used),
        "subject_mismatch": bool(subject_mismatch),
        "suggested_subject": suggested_subject,
        "clarified": bool(clarified),
        "duration_ms": round(float(duration_ms), 1),
        "reply_len": len(reply or ""),
        "stream": bool(stream),
    }


def emit_qa_trace(trace: dict[str, Any]) -> None:
    with _lock:
        _METRICS["turns"] = int(_METRICS["turns"]) + 1
        if trace.get("subject_mismatch"):
            _METRICS["mismatch_turns"] = int(_METRICS["mismatch_turns"]) + 1
        if trace.get("clarified"):
            _METRICS["clarify_turns"] = int(_METRICS["clarify_turns"]) + 1
        if trace.get("ocr_used"):
            _METRICS["ocr_turns"] = int(_METRICS["ocr_turns"]) + 1
        if trace.get("rag_used"):
            _METRICS["rag_turns"] = int(_METRICS["rag_turns"]) + 1
        _METRICS["total_ms"] = float(_METRICS["total_ms"]) + float(
            trace.get("duration_ms") or 0
        )

    try:
        payload = json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        payload = str(trace)
    logger.info(f"qa_trace {payload}")


class TurnTimer:
    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0
