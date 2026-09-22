"""分层情感。人格是角色底色，心情按句消退，这一句只提供信号。不另叫模型。"""

from __future__ import annotations

# 愉悦 -1..1，激动 0..1。只影响语气，不改人设。
BASELINE: dict[str, tuple[float, float]] = {
    "yuchen": (0.0, 0.35),
    "dani": (0.2, 0.28),
    "limo": (0.05, 0.12),
    "jiahui": (0.0, 0.22),
    "chenxue": (0.1, 0.72),
    "shanyu": (0.15, 0.18),
}

_DECAY = 0.7
_GAIN = 0.3

_LOW_WORDS = ("累", "烦", "不想", "放弃", "难过", "害怕", "焦虑", "崩溃", "无聊", "讨厌", "站不住")
_HIGH_WORDS = ("哈哈", "开心", "太好了", "兴奋", "想赢", "爽", "来比")


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def signal(text: str) -> tuple[float, float]:
    raw = text or ""
    if any(word in raw for word in _LOW_WORDS):
        return -0.8, 0.45
    if any(word in raw for word in _HIGH_WORDS):
        return 0.75, 0.8
    return 0.05, 0.25


def step(previous: dict | None, text: str) -> dict:
    """心情 = 0.7 × 上次 + 0.3 × 这一句。按孩子和本集记，不按角色各记一份。"""
    prev = previous or {}
    valence = float(prev.get("valence") or 0.0)
    arousal = 0.3 if prev.get("arousal") is None else float(prev.get("arousal") or 0.0)
    felt_v, felt_a = signal(text)
    return {
        "valence": round(_clip(_DECAY * valence + _GAIN * felt_v, -1.0, 1.0), 3),
        "arousal": round(_clip(_DECAY * arousal + _GAIN * felt_a, 0.0, 1.0), 3),
    }


def speak_tone(character_key: str, room: dict | None) -> str:
    """房间心情拉向这个人的底色，只写成语气，不把数字念出来。"""
    state = room or {}
    base_v, base_a = BASELINE.get(character_key, (0.0, 0.3))
    valence = 0.65 * float(state.get("valence") or 0.0) + 0.35 * base_v
    arousal = 0.65 * float(state.get("arousal") if state.get("arousal") is not None else 0.3) + 0.35 * base_a
    if valence <= -0.2:
        feel = "孩子这会儿偏低落，先接住，语气放软。"
    elif valence >= 0.2:
        feel = "孩子这会儿高兴，可以跟着有劲，但别压过他。"
    else:
        feel = "孩子情绪平稳，平常接话。"
    if arousal >= 0.55:
        feel += "句子可以短一点、冲一点，仍是你的口气。"
    elif arousal <= 0.22:
        feel += "不要突然提高嗓门。"
    return feel


def rank_speakers(
    *,
    mention: str | None,
    quote_who: str | None,
    last_who: str | None,
    text: str,
    affect: dict | None,
) -> list[str]:
    """被点名的先说。其余按激活分。默认 2 人，剧情问句可到 3 人：主答 + 旁听补句。"""
    from app.agents.academy.characters import CHARACTERS
    from app.agents.academy.harness import detect_intent

    state = affect or {}
    valence = float(state.get("valence") or 0.0)
    arousal = float(state.get("arousal") if state.get("arousal") is not None else 0.3)
    intent = detect_intent(text or "")
    pull = {
        "train": {"limo": 0.45, "jiahui": 0.35, "chenxue": 0.25, "dani": 0.2},
        "feel": {"dani": 0.5, "shanyu": 0.4, "jiahui": 0.25},
        "ep": {"yuchen": 0.45, "jiahui": 0.25, "chenxue": 0.2},
        "greet": {"dani": 0.35, "yuchen": 0.25, "chenxue": 0.15},
    }.get(intent, {})

    def score(key: str) -> float:
        _, base_a = BASELINE.get(key, (0.0, 0.3))
        value = 0.15 + 0.25 * base_a + float(pull.get(key) or 0)
        if key == mention:
            value += 3.0
        if key == quote_who:
            value += 1.6
        if key and key == last_who:
            value -= 1.0
        if valence <= -0.2 and key in ("dani", "shanyu"):
            value += 0.45
        if arousal >= 0.55 and key == "chenxue":
            value += 0.3
        return value

    ordered = sorted(CHARACTERS, key=score, reverse=True)
    speakers: list[str] = []
    if mention in CHARACTERS:
        speakers.append(mention)
    if quote_who in CHARACTERS and quote_who not in speakers:
        speakers.append(quote_who)
    # 用户视角剧情问：多人监听；点名/引用仍以 2 人为主，避免抢话
    raw = (text or "").strip()
    want = 2
    if mention or quote_who:
        want = 2
    elif intent in ("ep", "feel") or ("？" in raw or "?" in raw):
        want = 3
    elif len(raw) >= 10:
        want = 3
    for key in ordered:
        if len(speakers) >= want:
            break
        if key not in speakers:
            speakers.append(key)
    return speakers[:want]
