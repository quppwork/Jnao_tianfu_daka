"""剧集包 — 一集一套资料。见 docs/功能模块文档/天赋学院-剧集包模块.md"""

from app.agents.academy.packs.loader import (
    EpisodePack,
    all_packs,
    clear_pack_cache,
    get_pack,
    pack_fit,
    pack_lines,
    pack_sense,
    switchable_ids,
)

__all__ = [
    "EpisodePack",
    "all_packs",
    "clear_pack_cache",
    "get_pack",
    "pack_fit",
    "pack_lines",
    "pack_sense",
    "switchable_ids",
]
