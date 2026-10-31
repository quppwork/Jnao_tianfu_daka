"""知识源：本地料包必选；百炼检索可选。二者按集隔离合并。"""

from __future__ import annotations

from typing import Protocol

from app.agents.academy.knowledge.format import format_episode_notes
from app.agents.academy.knowledge.loader import get_knowledge
from app.agents.academy.knowledge.types import EpisodeKnowledge
from app.core.logger import get_logger

logger = get_logger("academy.knowledge")


class EpisodeKnowledgeProvider(Protocol):
    async def fetch_notes(
        self,
        *,
        episode_id: str,
        episode_title: str,
        user_text: str,
        character_key: str,
        knowledge_cutoff: str,
    ) -> str: ...


class LocalEpisodeKnowledgeProvider:
    """packs/<EP>/knowledge.yaml — 后续换数据只需改 YAML。"""

    async def fetch_notes(
        self,
        *,
        episode_id: str,
        episode_title: str,
        user_text: str,
        character_key: str,
        knowledge_cutoff: str,
    ) -> str:
        del episode_title, user_text, knowledge_cutoff
        know = get_knowledge(episode_id)
        return format_episode_notes(know, character_key=character_key)


class BailianEpisodeRetrieveProvider:
    """可选远端检索。未配置 index 时返回空；命中后仍按集裁剪。"""

    async def fetch_notes(
        self,
        *,
        episode_id: str,
        episode_title: str,
        user_text: str,
        character_key: str,
        knowledge_cutoff: str,
    ) -> str:
        del character_key
        from app.agents.academy.kb import academy_kb, clip_notes

        index_id = academy_kb().get("index_id") or ""
        if not index_id:
            return ""
        query = " ".join(
            part
            for part in (
                episode_id,
                episode_title,
                f"episode_id:{episode_id}",
                (user_text or "")[:60],
            )
            if part
        ).strip()
        if not query:
            return ""
        try:
            from app.services.bailian import rag_query

            result = await rag_query(
                query, index_id=index_id, top_n=4, timeout=8, mode="retrieve"
            )
        except Exception as e:
            logger.warning("academy bailian retrieve failed: %s", e)
            return ""
        if result is None or not result.nodes:
            return ""
        cutoff = (knowledge_cutoff or episode_id or "").strip().upper()
        return clip_notes([node.text for node in result.nodes], cutoff)


async def compose_episode_notes(
    *,
    episode_id: str,
    episode_title: str = "",
    user_text: str = "",
    character_key: str = "",
    knowledge_cutoff: str = "",
    local: EpisodeKnowledgeProvider | None = None,
    remote: EpisodeKnowledgeProvider | None = None,
    max_chars: int = 900,
) -> str:
    """本地 + 可选远端。本地永远优先写在前面。"""
    cutoff = (knowledge_cutoff or episode_id or "").strip().upper()
    eid = (episode_id or "").strip().upper()
    bits: list[str] = []
    local_p = local or LocalEpisodeKnowledgeProvider()
    remote_p = remote or BailianEpisodeRetrieveProvider()
    try:
        local_notes = await local_p.fetch_notes(
            episode_id=eid,
            episode_title=episode_title,
            user_text=user_text,
            character_key=character_key,
            knowledge_cutoff=cutoff,
        )
    except Exception as e:
        logger.warning("local episode knowledge failed: %s", e)
        local_notes = ""
    if local_notes:
        bits.append(local_notes)
    try:
        remote_notes = await remote_p.fetch_notes(
            episode_id=eid,
            episode_title=episode_title,
            user_text=user_text,
            character_key=character_key,
            knowledge_cutoff=cutoff,
        )
    except Exception as e:
        logger.warning("remote episode knowledge failed: %s", e)
        remote_notes = ""
    if remote_notes:
        bits.append(remote_notes)
    return "\n".join(bits).strip()[:max_chars]


def resolve_knowledge(episode_id: str | None) -> EpisodeKnowledge | None:
    return get_knowledge(episode_id)
