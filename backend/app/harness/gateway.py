"""数据面网关：认证、策略、审计、路由到沙箱 Executor。宿主不直接进沙箱跑命令。"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.harness.audit import audit_exec
from app.harness.control import SandboxError, SandboxSession, controller
from app.harness.policy import check_tool
from app.harness.protocol import ExecResult, ToolCall
from app.harness.registry import get_tool
from app.harness.settings import load_harness_settings


class GatewayError(SandboxError):
    pass


def invoke(
    tool: str,
    args: dict[str, Any] | None = None,
    *,
    timeout_s: float | None = None,
    session: SandboxSession | None = None,
    token: str | None = None,
) -> ExecResult:
    cfg = load_harness_settings()
    name = (tool or "").strip()
    t0 = time.perf_counter()
    timeout_ms = int((timeout_s if timeout_s is not None else cfg.sandbox_timeout_s) * 1000)
    call = ToolCall(
        tool=name,
        args=dict(args or {}),
        timeout_ms=timeout_ms,
        call_id=uuid.uuid4().hex[:10],
    )
    if name in ("python", "shell", "bash", "cmd", "powershell", "sh"):
        decision = check_tool(None, name)
    else:
        decision = check_tool(get_tool(name), name)
    if not decision.allowed:
        result = ExecResult(
            status="denied",
            exit_code=126,
            error=decision.reason,
        )
        _audit(session_id="gateway", tool=name, result=result, t0=t0)
        return result

    owned = False
    sess = session
    if sess is None:
        sess = controller.shared() if cfg.keepalive else controller.create()
        owned = not cfg.keepalive
    else:
        if token is not None and token != sess.token:
            result = ExecResult(status="denied", exit_code=401, error="invalid sandbox token")
            _audit(session_id=sess.id, tool=name, result=result, t0=t0)
            return result
    try:
        result = controller.exec(sess, call)
    except SandboxError as e:
        result = ExecResult(status="error", error=str(e)[:300], exit_code=1)
    finally:
        if owned and sess is not None:
            controller.destroy(sess)
    _audit(session_id=sess.id if sess else "-", tool=name, result=result, t0=t0)
    return result


async def invoke_async(
    tool: str,
    args: dict[str, Any] | None = None,
    *,
    timeout_s: float | None = None,
) -> ExecResult:
    import asyncio

    return await asyncio.to_thread(invoke, tool, args, timeout_s=timeout_s)


def _audit(*, session_id: str, tool: str, result: ExecResult, t0: float) -> None:
    blob = json.dumps(result.to_dict(), ensure_ascii=False)
    audit_exec(
        session_id=session_id,
        tool=tool,
        status=result.status,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        result_bytes=len(blob.encode("utf-8")),
        error=result.error,
    )
