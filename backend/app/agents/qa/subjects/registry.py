"""分学科 Agent 注册表"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.qa.subjects import chinese, english, math, science


@dataclass(frozen=True)
class SubjectAgent:
    key: str
    display_name: str
    role_prompt: str
    answer_style: str
    typical_topics: tuple[str, ...]


_REGISTRY: dict[str, SubjectAgent] = {
    "数学": SubjectAgent("math", "数学", math.ROLE_PROMPT, math.ANSWER_STYLE, math.TYPICAL_TOPICS),
    "语文": SubjectAgent("chinese", "语文", chinese.ROLE_PROMPT, chinese.ANSWER_STYLE, chinese.TYPICAL_TOPICS),
    "英语": SubjectAgent("english", "英语", english.ROLE_PROMPT, english.ANSWER_STYLE, english.TYPICAL_TOPICS),
    "科学": SubjectAgent("science", "科学", science.ROLE_PROMPT, science.ANSWER_STYLE, science.TYPICAL_TOPICS),
}


def get_subject_agent(subject: str | None) -> SubjectAgent | None:
    if not subject:
        return None
    return _REGISTRY.get(subject.strip())


def all_subjects() -> tuple[str, ...]:
    return tuple(_REGISTRY.keys())
