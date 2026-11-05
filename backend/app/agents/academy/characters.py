"""学院角色 — 图鉴键 + 角色卡。提示词只来自 cards/*.yaml，无代码内置人设/约束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.academy.cards import card_system_prompt, get_card


@dataclass(frozen=True)
class Character:
    key: str
    name: str
    tag: str


def _load_characters() -> dict[str, Character]:
    from app.agents.academy.cards import all_cards

    cards = all_cards()
    channel = {
        key: Character(key=card.key, name=card.name, tag=card.tag)
        for key, card in cards.items()
        if card.in_channel
    }
    if channel:
        return channel
    # 卡缺失时的最小图鉴（无口吻/约束）
    return {
        "shanyu": Character("shanyu", "善雨", "导师"),
        "yuchen": Character("yuchen", "章宇尘", "思者"),
        "dani": Character("dani", "施丹尼", "德者"),
        "limo": Character("limo", "李寞", "行者"),
        "jiahui": Character("jiahui", "王家慧", "学者"),
        "chenxue": Character("chenxue", "陈雪", "赢者"),
    }


CHARACTERS: dict[str, Character] = _load_characters()

TALENT_CHAR = {
    "思者": "yuchen",
    "赢者": "chenxue",
    "德者": "dani",
    "行者": "limo",
    "学者": "jiahui",
}

KIDS = ("yuchen", "dani", "chenxue", "limo", "jiahui")


def get_character(key: str) -> Character | None:
    return CHARACTERS.get(key)


def bot_id_for(character_key: str) -> str:
    return f"bot_{character_key.strip()}"


def system_prompt(
    char: Character,
    *,
    episode_title: str = "",
    task: str = "",
    child_talent: str = "",
    episode_id: str | None = None,
) -> str:
    """只注入角色卡；不再拼约束句、技能提示或剧情兜底。"""
    del episode_title, task, child_talent, episode_id
    card = get_card(char.key)
    if card:
        return card_system_prompt(card)
    return f"你是{char.name}。"
