"""Agent 板块标识 — 计费与用量按 feature 聚合，不绑具体 runner 实现。"""

from __future__ import annotations

from enum import StrEnum


class AgentFeature(StrEnum):
    GUIDE = "guide"
    PARENT_GUIDE = "parent_guide"
    QA = "qa"
    CONSULT = "consult"
    ACADEMY = "academy"
    SOLVE = "solve"
    REPORT_TALENT = "report_talent"
    HARNESS = "harness"
    RAG = "rag"
    UNKNOWN = "unknown"


_LABELS: dict[str, str] = {
    AgentFeature.GUIDE: "首页引导",
    AgentFeature.PARENT_GUIDE: "家长引导",
    AgentFeature.QA: "学科答疑",
    AgentFeature.CONSULT: "在线咨询",
    AgentFeature.ACADEMY: "学院对话",
    AgentFeature.SOLVE: "拍题解题",
    AgentFeature.REPORT_TALENT: "报告天赋解答",
    AgentFeature.HARNESS: "Harness",
    AgentFeature.RAG: "知识库检索",
    AgentFeature.UNKNOWN: "未分类",
}


def feature_label(feature: str | AgentFeature | None) -> str:
    key = str(feature or AgentFeature.UNKNOWN).strip() or AgentFeature.UNKNOWN
    return _LABELS.get(key, key)


def normalize_feature(feature: str | AgentFeature | None) -> str:
    raw = str(feature or "").strip()
    if not raw:
        return AgentFeature.UNKNOWN
    if raw.startswith("harness."):
        raw = raw.split(".", 1)[1]
    if raw.startswith("solve_"):
        return AgentFeature.SOLVE
    try:
        return AgentFeature(raw)
    except ValueError:
        return raw
