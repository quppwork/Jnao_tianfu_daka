"""Harness 运行时开关 — 本地默认 in-process + local 沙箱；生产可切 docker。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

SandboxMode = Literal["local", "docker"]
McpTransport = Literal["inprocess", "http"]


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip() in ("1", "true", "True", "yes")


@dataclass(frozen=True)
class HarnessSettings:
    sandbox: SandboxMode
    sandbox_image: str
    sandbox_timeout_s: float
    sandbox_memory_mb: int
    sandbox_pids: int
    max_result_bytes: int
    keepalive: bool
    mcp_transport: McpTransport
    mcp_token: str
    sandbox_deny: tuple[str, ...]
    mcp_deny: tuple[str, ...]
    mcp_expose: tuple[str, ...]
    protocol_version: str = "2024-11-05"
    server_name: str = "jnao-harness"
    server_version: str = "0.1.0"


def _csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def load_harness_settings() -> HarnessSettings:
    sandbox = (os.getenv("HARNESS_SANDBOX") or "local").strip().lower()
    if sandbox not in ("local", "docker"):
        sandbox = "local"
    transport = (os.getenv("HARNESS_MCP_TRANSPORT") or "inprocess").strip().lower()
    if transport not in ("inprocess", "http"):
        transport = "inprocess"
    timeout = float(os.getenv("HARNESS_SANDBOX_TIMEOUT", "20") or 20)
    mem = int(os.getenv("HARNESS_SANDBOX_MEMORY_MB", "128") or 128)
    pids = int(os.getenv("HARNESS_SANDBOX_PIDS", "64") or 64)
    max_bytes = int(os.getenv("HARNESS_SANDBOX_MAX_RESULT_BYTES", "65536") or 65536)
    return HarnessSettings(
        sandbox=sandbox,  # type: ignore[arg-type]
        sandbox_image=(os.getenv("HARNESS_SANDBOX_IMAGE") or "jnao-harness-sandbox:local").strip(),
        sandbox_timeout_s=max(1.0, timeout),
        sandbox_memory_mb=max(32, mem),
        sandbox_pids=max(8, pids),
        max_result_bytes=max(1024, max_bytes),
        keepalive=_flag("HARNESS_SANDBOX_KEEPALIVE", "0"),
        mcp_transport=transport,  # type: ignore[arg-type]
        mcp_token=(os.getenv("HARNESS_MCP_TOKEN") or "").strip(),
        sandbox_deny=_csv("HARNESS_SANDBOX_DENY"),
        mcp_deny=_csv("HARNESS_MCP_DENY"),
        mcp_expose=_csv("HARNESS_MCP_EXPOSE"),
    )


def mcp_http_enabled() -> bool:
    """HTTP MCP：开发默认开；生产须显式 HARNESS_MCP_HTTP=1。"""
    from app.core.security import is_production

    if is_production():
        return _flag("HARNESS_MCP_HTTP", "0")
    return _flag("HARNESS_MCP_HTTP", "1")
