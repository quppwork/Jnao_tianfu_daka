"""LLM 适配器 — 委托现有 harness.llm.route（DeepSeek / Doubao 等）。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


class _RouteCompletion:
    def __init__(self, route: Any) -> None:
        self._route = route

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await self._route.complete(messages, tools)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        async for tok in self._route.stream(messages, tools):
            yield tok


class ProfileLlmProvider:
    """实现 architecture.LlmProvider。"""

    def route(self, profile: str) -> _RouteCompletion:
        from app.harness.llm import route

        return _RouteCompletion(route(profile))

    def system_prompt(self, profile: str) -> str:
        from app.harness.llm import profile_system

        return profile_system(profile)
