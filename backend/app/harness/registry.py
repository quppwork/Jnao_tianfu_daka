"""统一工具注册表 — 业务 Agent 与 MCP 共用同一份 spec。"""

from __future__ import annotations

from typing import Any

from app.harness.types import ToolSpec

_TOOLS: dict[str, ToolSpec] = {}
_BOOTSTRAPPED = False


def register_tool(spec: ToolSpec) -> ToolSpec:
    _TOOLS[spec.name] = spec
    return spec


def get_tool(name: str) -> ToolSpec | None:
    ensure_builtin_tools()
    return _TOOLS.get(name)


def list_tool_specs(*, profile: str | None = None) -> list[ToolSpec]:
    ensure_builtin_tools()
    out = list(_TOOLS.values())
    if profile:
        out = [t for t in out if not t.profiles or profile in t.profiles]
    return sorted(out, key=lambda t: t.name)


def mcp_tool_list(*, profile: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
        }
        for t in list_tool_specs(profile=profile)
    ]


def ensure_builtin_tools() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED and _TOOLS:
        return
    from app.harness.tools import retrieve_kb as _rk
    from app.harness.tools import sandbox_ping as _sp
    from app.harness.tools import guide_wrap as _gw
    from app.harness.tools import parent_ops as _po
    from app.harness.tools import teacher_ops as _to
    from app.harness.tools import learn_ops as _lo
    from app.harness.tools import qa_ops as _qo

    _rk.register()
    _sp.register()
    _gw.register()
    _po.register()
    _to.register()
    _lo.register()
    _qo.register()
    _BOOTSTRAPPED = True


def reset_registry_for_tests() -> None:
    """仅测试用。"""
    global _BOOTSTRAPPED
    _TOOLS.clear()
    _BOOTSTRAPPED = False
