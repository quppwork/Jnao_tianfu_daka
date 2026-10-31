"""分频道 Agent 注册表 — 理科 / 文科 / 外语 / 科技 / 书法"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.qa.channel_policy import (
    CANONICAL_SUBJECTS,
    HARD_CONSTRAINTS,
    SOFT_CONSTRAINTS,
    normalize_subject,
)
from app.agents.qa.subjects import chinese, english, math, mind, science


@dataclass(frozen=True)
class SubjectAgent:
    key: str
    display_name: str
    role_prompt: str
    answer_style: str
    typical_topics: tuple[str, ...]
    soft_constraint: str = ""
    hard_constraint: str = ""


_REGISTRY: dict[str, SubjectAgent] = {
    "理科": SubjectAgent(
        "math",
        "理科",
        math.ROLE_PROMPT,
        math.ANSWER_STYLE,
        math.TYPICAL_TOPICS,
        soft_constraint=SOFT_CONSTRAINTS["理科"],
        hard_constraint=HARD_CONSTRAINTS["理科"],
    ),
    "文科": SubjectAgent(
        "chinese",
        "文科",
        chinese.ROLE_PROMPT,
        chinese.ANSWER_STYLE,
        chinese.TYPICAL_TOPICS,
        soft_constraint=SOFT_CONSTRAINTS["文科"],
        hard_constraint=HARD_CONSTRAINTS["文科"],
    ),
    "外语": SubjectAgent(
        "english",
        "外语",
        english.ROLE_PROMPT,
        english.ANSWER_STYLE,
        english.TYPICAL_TOPICS,
        soft_constraint=SOFT_CONSTRAINTS["外语"],
        hard_constraint=HARD_CONSTRAINTS["外语"],
    ),
    "科技": SubjectAgent(
        "science",
        "科技",
        science.ROLE_PROMPT,
        science.ANSWER_STYLE,
        science.TYPICAL_TOPICS,
        soft_constraint=SOFT_CONSTRAINTS["科技"],
        hard_constraint=HARD_CONSTRAINTS["科技"],
    ),
    "书法": SubjectAgent(
        "mind",
        "书法",
        mind.ROLE_PROMPT,
        mind.ANSWER_STYLE,
        mind.TYPICAL_TOPICS,
        soft_constraint=SOFT_CONSTRAINTS["书法"],
        hard_constraint=HARD_CONSTRAINTS["书法"],
    ),
}


def get_subject_agent(subject: str | None) -> SubjectAgent | None:
    key = normalize_subject(subject)
    if not key:
        return None
    return _REGISTRY.get(key)


def all_subjects() -> tuple[str, ...]:
    return CANONICAL_SUBJECTS
