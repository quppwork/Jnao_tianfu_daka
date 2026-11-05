"""兼容入口：数据面一律经 Gateway，不再让业务直接 subprocess。"""

from __future__ import annotations

from typing import Any

from app.harness.control import SandboxError
from app.harness.gateway import invoke_async
from app.harness.protocol import ExecResult

__all__ = ["SandboxError", "run_isolated"]


async def run_isolated(payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    tool = str(payload.get("tool") or "")
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    result: ExecResult = await invoke_async(tool, args, timeout_s=timeout)
    data = dict(result.data)
    data.setdefault("ok", result.ok)
    if result.error:
        data.setdefault("error", result.error)
    data["status"] = result.status
    data["exit_code"] = result.exit_code
    data["stdout"] = result.stdout
    data["stderr"] = result.stderr
    data["artifacts"] = result.artifacts
    if not result.ok:
        raise SandboxError(result.error or result.status)
    return data
