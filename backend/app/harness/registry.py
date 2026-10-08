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
    from app.harness.tools import ocr_ops as _ocr
    from app.harness.tools import web_lookup as _wl
    from app.harness.tools import math_sketch as _ms
    from app.harness.tools import solve_ops as _so

    _rk.register()
    _sp.register()
    _gw.register()
    _po.register()
    _to.register()
    _lo.register()
    _qo.register()
    _ocr.register()
    _wl.register()
    _ms.register()
    _so.register()
    from app.harness.gates import install_builtin_gates

    install_builtin_gates()
    _BOOTSTRAPPED = True


def reset_registry_for_tests() -> None:
    """仅测试用。"""
    global _BOOTSTRAPPED
    from app.harness.loop import clear_gates
    import app.harness.gates as _gates

    _TOOLS.clear()
    clear_gates()
    _gates._INSTALLED = False
    _BOOTSTRAPPED = False
