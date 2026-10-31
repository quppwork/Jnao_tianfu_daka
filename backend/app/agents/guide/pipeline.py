"""引导页编排路径 — 路由 →（RAG/工具）→ 生成 → 后处理。

`runner.run_chat` 按本模块的路径分支执行；后续 sub-agent / pipeline
步骤优先加在这里，避免业务散落在超长 runner 里。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from app.agents.shared.handoff import should_route_to_qa


class GuidePath(str, Enum):
    QA_HANDOFF = "qa_handoff"  # 学科解题 → 答疑按钮
    KB_AGENT = "kb_agent"  # 百炼选库 Agent
    LEGACY_RAG = "legacy_rag"  # 旧：工具块 + Retrieve + 豆包
    MINIMAL = "minimal"  # KB 未就绪时的短回复


def resolve_guide_path(
    message: str,
    *,
    kb_agent_ready: bool,
    use_legacy_when_kb_off: bool = True,
) -> GuidePath:
    """单轮入口路由（纯函数，易测）。"""
    if should_route_to_qa(message):
        return GuidePath.QA_HANDOFF
    if kb_agent_ready:
        return GuidePath.KB_AGENT
    if use_legacy_when_kb_off:
        return GuidePath.LEGACY_RAG
    return GuidePath.MINIMAL


def finalize_guide_payload(
    *,
    reply: str,
    meta: dict[str, Any],
    path: GuidePath | str,
) -> dict[str, Any]:
    """后处理：打上编排路径标记，供 trace / 前端排查。"""
    out = dict(meta)
    out["pipeline_path"] = path.value if isinstance(path, GuidePath) else str(path)
    text = (reply or "").strip()
    return {"reply": text, **out}


GuideStage = Literal[
    "route",
    "memory",
    "retrieve_or_tools",
    "generate",
    "postprocess",
]

PIPELINE_STAGES: tuple[GuideStage, ...] = (
    "route",
    "memory",
    "retrieve_or_tools",
    "generate",
    "postprocess",
)
