"""本轮工具上下文 — 不是跨模块统一 session。各业务表仍隔离。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

_CTX: ContextVar["ToolContext | None"] = ContextVar("harness_tool_ctx", default=None)


@dataclass
class ToolContext:
    db: Session | None = None
    actor_user_id: int = 0
    child_user_id: int = 0
    parent_user_id: int = 0
    profile: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def current_context() -> ToolContext:
    return _CTX.get() or ToolContext()


def bind_context(ctx: ToolContext):
    return _CTX.set(ctx)


def reset_context(token) -> None:
    _CTX.reset(token)


def context_from_args(args: dict[str, Any], *, profile: str | None) -> ToolContext:
    def _i(key: str) -> int:
        try:
            return int(args.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    child = _i("child_user_id") or _i("child_id")
    parent = _i("parent_user_id") or _i("parent_id")
    actor = _i("actor_user_id") or parent or child
    return ToolContext(
        actor_user_id=actor,
        child_user_id=child,
        parent_user_id=parent,
        profile=profile or "",
    )
