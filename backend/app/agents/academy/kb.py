"""天赋学院短剧知识库。只给讨论室检索，不进引导页和学科答疑的选库。"""

from __future__ import annotations

import os
import re

import yaml

from app.agents.academy.perception import episode_no
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
) -> str:
    """检索短剧库。失败或未配置时返回空，讨论照常进行。"""
    index_id = academy_kb()["index_id"]
    if not index_id:
        return ""
    query = " ".join(
        part
        for part in (episode_id, episode_title, " ".join(names), (user_text or "")[:60])
        if part
    ).strip()
    if not query:
        return ""
    try:
        from app.services.bailian import rag_query

        result = await rag_query(query, index_id=index_id, top_n=4, timeout=8, mode="retrieve")
    except Exception as e:
        logger.warning("academy drama retrieve failed: %s", e)
        return ""
    if result is None or not result.nodes:
        return ""
    return clip_notes([node.text for node in result.nodes], episode_id)
