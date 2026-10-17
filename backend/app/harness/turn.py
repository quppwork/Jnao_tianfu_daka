"""兼容入口 — 委托 app.runtime（组装后的 Executor）。

新代码请：from app.runtime import run_turn, run_turn_stream
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.harness.context import ToolContext
from app.harness.types import ToolResult
from app.runtime.public import public_turn

# 旧测试 / patch 路径兼容
_public_turn = public_turn


async def run_profile_turn(
    profile: str,
    user_message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    system_extra: str = "",
    system_override: str | None = None,
    max_steps: int = 6,
    thread_id: str | None = None,
    model: Any | None = None,
    allow_tools: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.runtime import run_turn

    return await run_turn(
        profile,
        user_message,
        history=history,
        ctx=ctx,
        system_extra=system_extra,
        system_override=system_override,
        max_steps=max_steps,
        thread_id=thread_id,
        model=model,
        allow_tools=allow_tools,
        metadata=metadata,
        fresh=True,
    )


async def run_profile_turn_stream(
    profile: str,
    user_message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    ctx: ToolContext | None = None,
    system_extra: str = "",
    system_override: str | None = None,
    max_steps: int = 6,
    thread_id: str | None = None,
    model: Any | None = None,
    allow_tools: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    from app.runtime import run_turn_stream

    async for item in run_turn_stream(
        profile,
        user_message,
        history=history,
        ctx=ctx,
        system_extra=system_extra,
        system_override=system_override,
        max_steps=max_steps,
        thread_id=thread_id,
        model=model,
        allow_tools=allow_tools,
        metadata=metadata,
        fresh=True,
    ):
        yield item


def tool_result_brief(result: ToolResult | None) -> dict[str, Any]:
    if result is None:
        return {"ok": False}
    return result.to_audit() | {"data": result.data}
