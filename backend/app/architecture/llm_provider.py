"""LLM 怎么调 — 契约。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class LlmCompletion(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]: ...


class LlmProvider(Protocol):
    """按 profile 路由到具体模型客户端。"""

    def route(self, profile: str) -> LlmCompletion: ...

    def system_prompt(self, profile: str) -> str: ...
