"""分集讨论知识 — 数据结构。与 pack.yaml（UI/频道）解耦。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EpisodeKnowledge:
    """一集讨论可用的「料包」。后续百炼切片应对齐同一字段语义。"""

    episode_id: str
    title: str = ""
    synopsis: str = ""
    beats: tuple[str, ...] = ()
    character_beats: dict[str, str] = field(default_factory=dict)
    can_talk: tuple[str, ...] = ()
    cannot_know: tuple[str, ...] = ()
    spoilers_block: tuple[str, ...] = ()
    # 可选：match → seed，仅作事实锚点，不作为台词模板
    facts: tuple[dict, ...] = ()

    @property
    def empty(self) -> bool:
        return not (
            self.synopsis
            or self.beats
            or self.character_beats
            or self.can_talk
            or self.cannot_know
        )
