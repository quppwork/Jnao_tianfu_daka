"""双重策略：沙箱允许列表 ∩ MCP 允许列表。缺一不可，防止 MCP loopback 绕过 deny。"""

from __future__ import annotations

from dataclasses import dataclass

from app.harness.protocol import DENIED_TOOLS
from app.harness.settings import load_harness_settings
from app.harness.types import ToolSpec

HARD_DENY = DENIED_TOOLS
MAX_USER_CHARS = 16000


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


def check_tool(spec: ToolSpec | None, name: str, *, profile: str | None = None) -> PolicyDecision:
    cfg = load_harness_settings()
    tool = (name or "").strip()
    if not tool:
        return PolicyDecision(False, "empty tool name")
    if tool in HARD_DENY:
        return PolicyDecision(False, f"hard-deny {tool}")
    if tool in cfg.sandbox_deny:
        return PolicyDecision(False, f"sandbox.deny {tool}")
    if tool in cfg.mcp_deny:
        return PolicyDecision(False, f"mcp.deny {tool}")
    if spec is None:
        return PolicyDecision(False, f"unknown tool {tool}")
    if profile and spec.profiles and profile not in spec.profiles:
        return PolicyDecision(False, f"profile {profile} cannot use {tool}")
    if cfg.mcp_expose and tool not in cfg.mcp_expose:
        return PolicyDecision(False, f"mcp catalog hides {tool}")
    if spec.plane == "sandbox" and tool in cfg.sandbox_deny:
        return PolicyDecision(False, f"sandbox.deny {tool}")
    return PolicyDecision(True)


def check_user_message(text: str) -> PolicyDecision:
    raw = text or ""
    if len(raw) > MAX_USER_CHARS:
        return PolicyDecision(False, f"message exceeds {MAX_USER_CHARS} chars")
    return PolicyDecision(True)


def visible_specs(specs: list[ToolSpec], *, profile: str | None = None) -> list[ToolSpec]:
    out: list[ToolSpec] = []
    for spec in specs:
        if check_tool(spec, spec.name, profile=profile).allowed:
            out.append(spec)
    return out
