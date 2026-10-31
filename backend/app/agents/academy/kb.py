"""天赋学院知识注入：分集料包（本地）+ 全局图认知 + 可选百炼检索。不做台词兜底。"""

from __future__ import annotations

import os
import re

import yaml

from app.agents.academy.perception import episode_no
from app.agents.academy.world import character_knowledge, character_mood
from app.core.logger import get_logger
from app.services.kb_registry import resolve_registry_path

logger = get_logger("academy.kb")

_EP = re.compile(r"E(\d{2})")
_WITHHOLD = re.compile(r"绑架|胃癌|病房|母亲离开|一寸照片|安全屋|保姆")


def academy_kb() -> dict[str, str]:
    """知识管理 index_id + 知识问答 aid。环境变量可覆盖 yaml。"""
    data: dict = {}
    path = resolve_registry_path()
    if path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        block = raw.get("academy") if isinstance(raw, dict) else None
        if isinstance(block, dict):
            data = block
    index_id = (os.getenv("BAILIAN_ACADEMY_INDEX_ID") or data.get("index_id") or "").strip()
    aid = (os.getenv("BAILIAN_ACADEMY_QA_AID") or data.get("aid") or "").strip()
    return {"index_id": index_id, "aid": aid}


def clip_notes(chunks: list[str], episode_id: str) -> str:
    """丢掉晚于本集的切片，以及不该进对话的伤口。"""
    current = episode_no(episode_id)
    kept: list[str] = []
    for raw in chunks:
        text = (raw or "").strip()
        if not text or _WITHHOLD.search(text):
            continue
        later = [int(n) for n in _EP.findall(text) if int(n) > current]
        if later:
            continue
        # 特辑 cutoff（EH*/ES*）时，clip 以传入 id 文本是否自称更晚集为准
        eid = (episode_id or "").strip().upper()
        if eid.startswith("E") and eid[1:].isdigit():
            pass
        kept.append(text)
        if len(kept) >= 3:
            break
    return "\n".join(kept)[:700]


async def drama_notes(
    *,
    names: list[str],
    episode_id: str,
    episode_title: str,
    user_text: str = "",
    character_key: str = "",
    knowledge_cutoff: str = "",
) -> str:
    """
    角色认知 = 分集料包（本地）+ 全局图 + 可选百炼。
    无命中则返回空字符串，禁止用样例台词填充。
    """
    del names
    from app.agents.academy.knowledge import compose_episode_notes

    cutoff = (knowledge_cutoff or episode_id or "").strip().upper()
    bits: list[str] = []

    episode_block = await compose_episode_notes(
        episode_id=episode_id,
        episode_title=episode_title,
        user_text=user_text,
        character_key=character_key,
        knowledge_cutoff=cutoff,
    )
    if episode_block:
        bits.append(episode_block)

    known = character_knowledge(character_key, cutoff=cutoff) if character_key else ""
    if known:
        bits.append(known)
    mood = character_mood(character_key, episode_id) if character_key else ""
    if mood:
        bits.append(mood)

    return "\n".join(bits)[:900]
