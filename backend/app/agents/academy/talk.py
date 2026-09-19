"""讨论区的 @、引用和表情。表情用系统 Unicode，不接 QQ / 微信版权包。"""

from __future__ import annotations

import re

from app.agents.academy.characters import CHARACTERS

# 聊天里现在最常见的一档，和微信、QQ 输入法里的系统表情同一套字形。
STICKERS = (
    "😂", "🤣", "😭", "😅", "🥹", "🥺", "😏", "🙄", "🤔", "😤",
    "🥰", "😎", "🙈", "🫠", "👍", "👏", "❤️", "🔥", "✨", "💪",
    "🤝", "👀", "🙏", "👋", "💯", "😴", "🤡", "😮", "🐶", "📒",
)

_ALIAS = {key: key for key in CHARACTERS}
for _key, _char in CHARACTERS.items():
    _ALIAS[_char.name] = _key
    _ALIAS[_char.tag] = _key
_ALIAS.update({"宇尘": "yuchen", "丹尼": "dani", "善雨导师": "shanyu"})

_AT = re.compile(r"@([^\s@]{1,8})")


def sticker_pack() -> dict:
    return {
        "source": "unicode",
        "note": "系统常用表情。微信和 QQ 的表情包没有开放接口，图也不能直接搬。",
        "small": list(STICKERS),
        "big": list(STICKERS[:16]),
    }


def resolve_mention(text: str | None, explicit: str | None) -> str | None:
    key = _alias(explicit)
    if key:
        return key
    for hit in _AT.findall(text or ""):
        key = _alias(hit)
        if key:
            return key
    return None


def clean_quote(quote) -> dict | None:
    if not isinstance(quote, dict):
        return None
    who = str(quote.get("who") or "").strip()
    if who.startswith("bot_"):
        who = who[4:]
    text = " ".join(str(quote.get("text") or "").split())[:80]
    if not text or (who not in CHARACTERS and who != "me"):
        return None
    return {"who": who, "text": text}


def clean_sticker(value: str | None) -> str | None:
    face = (value or "").strip()
    if face in STICKERS:
        return face
    return None


def build_user_line(
    text: str | None,
    mention: str | None = None,
    quote=None,
    sticker: str | None = None,
) -> dict | None:
    content = " ".join((text or "").split())[:200]
    mark = resolve_mention(content, mention)
    quoted = clean_quote(quote)
    face = clean_sticker(sticker)
    if mark:
        name = CHARACTERS[mark].name
        if f"@{name}" not in content and f"@{mark}" not in content:
            content = f"@{name} {content}".strip()
    if not content and face:
        content = face
    if not content:
        return None
    row = {"who": "me", "text": content}
    if mark:
        row["mention"] = mark
    if quoted:
        row["quote"] = quoted
    if face and face != content:
        row["sticker"] = face
    return row


def _alias(raw: str | None) -> str | None:
    token = (raw or "").strip()
    if token.startswith("bot_"):
        token = token[4:]
    return _ALIAS.get(token)
