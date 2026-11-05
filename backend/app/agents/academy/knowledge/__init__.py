"""分集讨论知识层 — 与 pack UI 配置解耦；本地 YAML + 可选百炼。"""

from app.agents.academy.knowledge.format import (
    boundary_line,
    character_perspective,
    format_episode_notes,
    knowledge_fact_seed,
    knowledge_synopsis,
)
from app.agents.academy.knowledge.loader import (
    all_knowledge,
    clear_knowledge_cache,
    get_knowledge,
)
from app.agents.academy.knowledge.provider import (
    BailianEpisodeRetrieveProvider,
    LocalEpisodeKnowledgeProvider,
    compose_episode_notes,
    resolve_knowledge,
)
from app.agents.academy.knowledge.types import EpisodeKnowledge

__all__ = [
    "BailianEpisodeRetrieveProvider",
    "EpisodeKnowledge",
    "LocalEpisodeKnowledgeProvider",
    "all_knowledge",
    "boundary_line",
    "character_perspective",
    "clear_knowledge_cache",
    "compose_episode_notes",
    "format_episode_notes",
    "get_knowledge",
    "knowledge_fact_seed",
    "knowledge_synopsis",
    "resolve_knowledge",
]
