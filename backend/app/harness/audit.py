"""沙箱审计 — 只记元数据，不把 stdout 全文打进日志。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("jnao.harness.audit")


def audit_exec(
    *,
    session_id: str,
    tool: str,
    status: str,
    duration_ms: int,
    result_bytes: int,
    error: str | None = None,
) -> None:
    logger.info(
        "sandbox.exec sid=%s tool=%s status=%s ms=%s bytes=%s err=%s",
        session_id,
        tool,
        status,
        duration_ms,
        result_bytes,
        (error or "-")[:120],
    )


def audit_control(action: str, *, session_id: str, extra: dict[str, Any] | None = None) -> None:
    bits = " ".join(f"{k}={v}" for k, v in (extra or {}).items())
    logger.info("sandbox.ctrl action=%s sid=%s %s", action, session_id, bits)


def audit_loop(
    action: str,
    *,
    thread_id: str,
    profile: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    bits = " ".join(f"{k}={v}" for k, v in (extra or {}).items())
    logger.info(
        "agent.loop action=%s thread=%s profile=%s %s",
        action,
        thread_id,
        profile or "-",
        bits,
    )
