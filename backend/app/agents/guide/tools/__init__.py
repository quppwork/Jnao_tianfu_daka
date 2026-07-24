"""只读工具注册表 — 阶段 B 供 runner tool-loop 使用。

A0 开场不走本目录（由 context/situations 固定查库）。
工具必须只读、短输出、可审计。
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

ToolFn = Callable[[Session, int, dict], Any]

# name -> callable；具体实现见同包各模块
TOOL_REGISTRY: dict[str, ToolFn] = {}


def register(name: str):
    def deco(fn: ToolFn) -> ToolFn:
        TOOL_REGISTRY[name] = fn
        return fn
    return deco


def list_tools() -> list[str]:
    # 确保内置工具已加载
    from app.agents.guide.tools import profile as _p  # noqa: F401
    from app.agents.guide.tools import today_plan as _t  # noqa: F401
    from app.agents.guide.tools import checkin_timeline as _c  # noqa: F401
    from app.agents.guide.tools import skill_progress as _s  # noqa: F401
    from app.agents.guide.tools import suggest_next as _n  # noqa: F401
    from app.agents.guide.tools import talent_report as _tr  # noqa: F401

    return sorted(TOOL_REGISTRY.keys())


def call_tool(db: Session, child_user_id: int, name: str, args: dict | None = None) -> Any:
    if name not in TOOL_REGISTRY:
        list_tools()
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        raise KeyError(f"unknown guide tool: {name}")
    return fn(db, child_user_id, args or {})
