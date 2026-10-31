"""组装层 — 依赖注入（对照 main.js）。

启动时或首次调用 get_bundle() 时装配：
  architecture 契约 ← providers / memory / harness.guards ← runtime.Executor
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.harness.guards.composite import CompositeGuard, default_guards
from app.memory.checkpoint import CheckpointStore
from app.providers.llm.profile_router import ProfileLlmProvider
from app.providers.mcp.gateway import GatewayMcpProvider
from app.runtime.executor import Executor


@dataclass
class AgentBundle:
    """一次装配好的 Agent 运行时依赖。"""

    llm: ProfileLlmProvider
    mcp: GatewayMcpProvider
    checkpoint: CheckpointStore
    guards: CompositeGuard
    executor: Executor


_BUNDLE: AgentBundle | None = None


def build_bundle(*, guards: CompositeGuard | None = None) -> AgentBundle:
    g = guards or default_guards()
    llm = ProfileLlmProvider()
    mcp = GatewayMcpProvider()
    checkpoint = CheckpointStore()
    executor = Executor(guards=g, llm=llm, mcp=mcp, checkpoint=checkpoint)
    return AgentBundle(
        llm=llm,
        mcp=mcp,
        checkpoint=checkpoint,
        guards=g,
        executor=executor,
    )


def get_bundle() -> AgentBundle:
    global _BUNDLE
    if _BUNDLE is None:
        _BUNDLE = build_bundle()
    return _BUNDLE


def reset_bundle(bundle: AgentBundle | None = None) -> AgentBundle:
    """测试用：替换或重建全局装配。"""
    global _BUNDLE
    _BUNDLE = bundle or build_bundle()
    return _BUNDLE


def wire_legacy_harness() -> None:
    """确保旧 harness.turn 与 runtime 共用同一套 guards（幂等）。"""
    get_bundle()
