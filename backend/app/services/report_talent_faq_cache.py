"""报告页通用问答 Redis 缓存（不含个人报告上下文的回答）。"""

from __future__ import annotations

import hashlib
import re

from app.core.cache import cache_get_json, cache_set_json, ttl_env

_PUNCT = re.compile(r"[\s\?？!！。．\.\,，、；;：:\"'“”‘’]+")


def normalize_question(question: str) -> str:
    q = (question or "").strip().lower()
    q = _PUNCT.sub("", q)
    return q


def cache_key_for_question(question: str, *, talent: str = "") -> str:
    norm = normalize_question(question)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
    t = (talent or "").strip()[:16]
    return f"jnao:report_talent:faq:{t}:{digest}"


def get_cached_reply(question: str, *, talent: str = "") -> str | None:
    raw = cache_get_json(cache_key_for_question(question, talent=talent))
    if isinstance(raw, dict):
        reply = str(raw.get("reply") or "").strip()
        return reply or None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def set_cached_reply(question: str, reply: str, *, talent: str = "") -> None:
    text = (reply or "").strip()
    if not text:
        return
    ttl = ttl_env("CACHE_TTL_REPORT_TALENT_FAQ", 86400)
    cache_set_json(
        cache_key_for_question(question, talent=talent),
        {"reply": text},
        ttl,
    )
