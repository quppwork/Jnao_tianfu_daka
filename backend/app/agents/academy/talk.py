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

# 给模型看的口语提示：纯表情时否则模型常当乱码/忽略
STICKER_HINTS: dict[str, str] = {
    "😂": "大笑",
    "🤣": "笑到前仰后合",
    "😭": "大哭/破防",
    "😅": "尴尬或无奈地笑",
    "🥹": "感动想哭",
    "🥺": "可怜巴巴/撒娇求回应",
    "😏": "坏笑/调侃",
    "🙄": "翻白眼/无语",
    "🤔": "在想/疑惑",
    "😤": "不服气/较劲",
    "🥰": "开心喜欢",
    "😎": "得意酷",
    "🙈": "害羞捂脸",
    "🫠": "无语到融化",
    "👍": "点赞认同",
    "👏": "鼓掌",
    "❤️": "比心喜欢",
    "🔥": "太燃了",
    "✨": "闪光/好看",
    "💪": "加油鼓劲",
    "🤝": "握手达成",
    "👀": "在看/围观",
    "🙏": "拜托或感谢",
    "👋": "打招呼",
    "💯": "满分赞同",
    "😴": "困了想睡",
    "🤡": "自嘲像个小丑",
    "😮": "惊讶",
    "🐶": "卖萌",
    "📒": "记笔记",
}

_ALIAS = {key: key for key in CHARACTERS}
for _key, _char in CHARACTERS.items():
    _ALIAS[_char.name] = _key
    _ALIAS[_char.tag] = _key
_ALIAS.update({"宇尘": "yuchen", "丹尼": "dani", "善雨导师": "shanyu"})

_AT = re.compile(r"@([^\s@]{1,8})")
# 单枚系统表情（含部分组合序列）；拒绝 HTML / 过长串
_EMOJI_TOKEN = re.compile(
    r"^("
    r"[\U0001F300-\U0001FAFF]"
    r"|[\U0001F1E0-\U0001F1FF]{2}"
    r"|[\u2600-\u27BF]"
    r"|❤️|✨|💯|‼️|⁉️"
    r")([\U0001F3FB-\U0001F3FF]|[\uFE0F\u200D].*)?$"
)


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
    if not face or len(face) > 16 or "<" in face or ">" in face:
        return None
    if face in STICKERS:
        return face
    if _EMOJI_TOKEN.match(face):
        return face
    return None


def _only_sticker_text(text: str) -> str | None:
    """正文若只有 1～3 个表情，整段当贴纸。"""
    raw = (text or "").strip()
    if not raw or len(raw) > 24:
        return None
    parts = re.findall(
        r"[\U0001F300-\U0001FAFF]"
        r"|[\U0001F1E0-\U0001F1FF]{2}"
        r"|[\u2600-\u27BF]"
        r"|❤️|✨|💯"
        r"(?:[\U0001F3FB-\U0001F3FF]|\uFE0F)?",
        raw,
    )
    joined = "".join(parts)
    # 去掉零宽/变体后应与原文一致
    compact = re.sub(r"[\s\uFE0F\u200D]", "", raw)
    joined_c = re.sub(r"[\s\uFE0F\u200D]", "", joined)
    if not parts or joined_c != compact:
        return None
    if len(parts) == 1:
        return clean_sticker(parts[0]) or parts[0]
    if 1 < len(parts) <= 3:
        return joined
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
    # 只有前端点「大表情」传来的 sticker 才落库为大图；小表情只是普通正文
    face = clean_sticker(sticker)
    if mark:
        name = CHARACTERS[mark].name
        if f"@{name}" not in content and f"@{mark}" not in content:
            content = f"@{name} {content}".strip()
    if not content and face:
        content = face
    if not content:
        return None
    row: dict = {"who": "me", "text": content}
    if mark:
        row["mention"] = mark
    if quoted:
        row["quote"] = quoted
    if face:
        row["sticker"] = face
    return row


def annotate_for_model(row: dict) -> str:
    """把表情翻成口语提示，避免模型把纯 emoji 当噪声。"""
    text = str(row.get("text") or "").strip()
    face = str(row.get("sticker") or "").strip() or None
    if not face:
        face = _only_sticker_text(text)
    if not face:
        return text
    hint = STICKER_HINTS.get(face)
    if not hint and len(face) <= 8:
        hint = "发了一个表情"
    if not hint:
        return text
    if not text or text == face or _only_sticker_text(text) == face:
        return (
            f"（对方发了表情{face}，意思大概是：{hint}。"
            f"请用一两句口语接住这个表情，不要复读表情符号，也不要说「我看不懂表情」。）"
        )
    return f"{text}（还带了表情{face}，大概是：{hint}）"


def _alias(raw: str | None) -> str | None:
    token = (raw or "").strip()
    if token.startswith("bot_"):
        token = token[4:]
    return _ALIAS.get(token)
