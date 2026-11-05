"""轮换选取 — visit_key / user_id 稳定洗牌，同类型共用。"""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any, Sequence

from app.suggest_prompts.types import SuggestChip


def seed_int(*parts: Any) -> int:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return int(hashlib.md5(raw.encode("utf-8")).hexdigest()[:8], 16)


def pick_from_pool(
    pool: Sequence[SuggestChip],
    *,
    limit: int,
    seed_parts: Sequence[Any],
) -> list[SuggestChip]:
    limit = max(1, min(int(limit or 3), 12))
    if not pool:
        return []
    parts = list(seed_parts)
    if not parts or parts[-1] in (None, ""):
        parts = [*parts[:-1], secrets.token_hex(8)] if parts else [secrets.token_hex(8)]
    rng = random.Random(seed_int(*parts))
    picked = list(pool)
    rng.shuffle(picked)
    return picked[:limit]
