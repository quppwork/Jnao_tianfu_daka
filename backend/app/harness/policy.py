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


def profile_tool_allowlist(profile: str | None) -> frozenset[str] | None:
    """PROFILES[profile].tools 非空时返回白名单；None 表示不额外收窄。"""
    if not profile:
        return None
    from app.harness.llm import get_profile, resolve_profile_name

    cfg = get_profile(resolve_profile_name(profile))
    raw = cfg.get("tools")
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    names = frozenset(str(x).strip() for x in raw if str(x).strip())
    return names or None


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
    allow = profile_tool_allowlist(profile)
    if allow is not None and tool not in allow:
        return PolicyDecision(False, f"profile {profile} tools allowlist excludes {tool}")
    if cfg.mcp_expose and tool not in cfg.mcp_expose:
        return PolicyDecision(False, f"mcp catalog hides {tool}")
    if spec.plane == "sandbox" and tool in cfg.sandbox_deny:
        return PolicyDecision(False, f"sandbox.deny {tool}")
    return PolicyDecision(True)


def check_user_message(text: str, *, profile: str | None = None) -> PolicyDecision:
    """用户输入策略：长度 + 提示词注入（Harness 共用，各 profile 生效）。"""
    del profile  # 判定本身与 profile 无关；拒识文案由调用方按 profile 选取
    raw = text or ""
    if len(raw) > MAX_USER_CHARS:
        return PolicyDecision(False, f"message exceeds {MAX_USER_CHARS} chars")
    from app.harness.safety import looks_like_prompt_injection

    if looks_like_prompt_injection(raw):
        return PolicyDecision(False, "prompt_injection")
    return PolicyDecision(True)


def visible_specs(specs: list[ToolSpec], *, profile: str | None = None) -> list[ToolSpec]:
    out: list[ToolSpec] = []
    for spec in specs:
        if check_tool(spec, spec.name, profile=profile).allowed:
            out.append(spec)
    return out
