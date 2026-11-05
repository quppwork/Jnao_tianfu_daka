"""沙箱内 Executor（数据面）。宿主只通过 stdin/stdout JSON 通话。

本地: python -u scripts/harness_sandbox_agent.py --loop
Docker: 同入口，stdin 一条 exec 消息或 JSONL。
不执行任意 python/shell。
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

ALLOWED = frozenset({"sandbox.ping", "sandbox.health"})
DENIED = frozenset({"python", "shell", "bash", "cmd", "powershell", "sh"})


def _clip(text: str, limit: int = 65536) -> str:
    raw = (text or "").encode("utf-8")
    if len(raw) <= limit:
        return text or ""
    return raw[: limit - 3].decode("utf-8", errors="ignore") + "..."


def dispatch(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    name = (tool or "").strip()
    if name in DENIED:
        return {
            "status": "denied",
            "exit_code": 126,
            "error": f"tool {name} is not allowed in sandbox",
            "data": {},
            "stdout": "",
            "stderr": "",
            "artifacts": [],
        }
    if name not in ALLOWED:
        return {
            "status": "denied",
            "exit_code": 126,
            "error": f"sandbox denies tool {name}",
            "data": {},
            "stdout": "",
            "stderr": "",
            "artifacts": [],
        }
    if name == "sandbox.health":
        return {
            "status": "success",
            "exit_code": 0,
            "data": {"alive": True, "via": "sandbox-agent"},
            "stdout": "ok\n",
            "stderr": "",
            "artifacts": [],
        }
    token = str((args or {}).get("token") or "ok")[:80]
    line = f"pong:{token}\n"
    return {
        "status": "success",
        "exit_code": 0,
        "data": {"ok": True, "pong": token, "via": "sandbox"},
        "stdout": line,
        "stderr": "",
        "artifacts": [],
    }


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    op = str(msg.get("op") or "exec")
    if op == "shutdown":
        return None
    if op == "health":
        return {
            "id": msg.get("id") or "",
            "status": "success",
            "exit_code": 0,
            "data": {"alive": True},
            "stdout": "",
            "stderr": "",
            "artifacts": [],
            "duration_ms": 0,
        }
    if op == "mcp":
        return _mcp_inside(msg)
    t0 = time.perf_counter()
    tool = str(msg.get("tool") or "")
    args = msg.get("args") if isinstance(msg.get("args"), dict) else {}
    out = dispatch(tool, args)
    out["id"] = msg.get("id") or ""
    out["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    out["stdout"] = _clip(str(out.get("stdout") or ""))
    out["stderr"] = _clip(str(out.get("stderr") or ""), 8192)
    return out


def _mcp_inside(msg: dict[str, Any]) -> dict[str, Any]:
    """沙箱内 MCP（Mode A）：不 bind 端口，只处理宿主经 stdio 转过来的 JSON-RPC。"""
    rpc = msg.get("rpc") if isinstance(msg.get("rpc"), dict) else {}
    method = str(rpc.get("method") or "")
    params = rpc.get("params") if isinstance(rpc.get("params"), dict) else {}
    t0 = time.perf_counter()
    if method == "tools/list":
        tools = [
            {"name": "sandbox.ping", "description": "sandbox ping", "plane": "sandbox"},
            {"name": "sandbox.health", "description": "sandbox health", "plane": "sandbox"},
        ]
        data = {"tools": tools}
        return {
            "id": msg.get("id") or "",
            "status": "success",
            "exit_code": 0,
            "data": data,
            "stdout": "",
            "stderr": "",
            "artifacts": [],
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }
    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        out = dispatch(name, args)
        out["id"] = msg.get("id") or ""
        out["duration_ms"] = int((time.perf_counter() - t0) * 1000)
        return out
    return {
        "id": msg.get("id") or "",
        "status": "error",
        "exit_code": 2,
        "error": f"unknown mcp method {method}",
        "data": {},
        "stdout": "",
        "stderr": "",
        "artifacts": [],
        "duration_ms": int((time.perf_counter() - t0) * 1000),
    }


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def loop() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _write({"status": "error", "error": "invalid json", "exit_code": 2})
            continue
        if not isinstance(msg, dict):
            _write({"status": "error", "error": "invalid request", "exit_code": 2})
            continue
        reply = handle(msg)
        if reply is None:
            return 0
        _write(reply)
    return 0


def oneshot(raw: str) -> int:
    raw = (raw or "").strip()
    if not raw:
        _write({"status": "error", "error": "empty request", "exit_code": 2})
        return 2
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        # 兼容旧 job.json：{"tool","args"}
        _write({"status": "error", "error": "invalid json", "exit_code": 2})
        return 2
    if not isinstance(msg, dict):
        _write({"status": "error", "error": "invalid request", "exit_code": 2})
        return 2
    if "op" not in msg:
        msg = {"op": "exec", **msg}
    reply = handle(msg) or {"status": "success", "exit_code": 0}
    _write(reply)
    return 0 if reply.get("status") == "success" else 1


def main(argv: list[str]) -> int:
    if "--loop" in argv:
        return loop()
    if len(argv) >= 2 and not argv[1].startswith("-"):
        from pathlib import Path

        return oneshot(Path(argv[1]).read_text(encoding="utf-8"))
    return oneshot(sys.stdin.read())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
