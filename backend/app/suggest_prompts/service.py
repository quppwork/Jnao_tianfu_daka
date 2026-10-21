"""提问引导服务 — 三业务统一入口。"""

from __future__ import annotations

from typing import Any

from app.suggest_prompts.pools import pool_for
from app.suggest_prompts.rotate import pick_from_pool
from app.suggest_prompts.types import SuggestAudience, SuggestChip


def _normalize_audience(audience: str) -> SuggestAudience:
    if audience in ("report", "student", "parent", "qa"):
        return audience  # type: ignore[return-value]
    if audience in ("guide", "guide_child", "child"):
        return "student"
    if audience in ("guide_parent", "parent_guide"):
        return "parent"
    if audience in ("report_talent", "talent_report"):
        return "report"
    return "student"


def pick_suggest_prompts(
    audience: str = "student",
    *,
    limit: int = 3,
    user_id: int | None = None,
    visit_key: str | None = None,
    talent: str | None = None,
) -> list[dict[str, Any]]:
    """返回本轮展示的 chips（dict）。

    - student/parent/qa → {label, text}
    - report → {q, hot}
    """
    aud = _normalize_audience(audience)
    pool = pool_for(aud)
    chips = pick_from_pool(
        pool,
        limit=limit,
        seed_parts=(aud, user_id, visit_key),
    )
    talent_s = (talent or "").strip()
    out: list[dict[str, Any]] = []
    for c in chips:
        r = c.rendered(talent=talent_s) if talent_s or "{talent}" in (c.label + c.text) else c
        if aud == "report":
            out.append(r.as_report_item())
        else:
            out.append(r.as_guide_item())
    return out


def suggest_prompts_payload(
    audience: str = "student",
    *,
    limit: int = 3,
    user_id: int | None = None,
    visit_key: str | None = None,
    talent: str | None = None,
) -> dict[str, Any]:
    aud = _normalize_audience(audience)
    items = pick_suggest_prompts(
        aud,
        limit=limit,
        user_id=user_id,
        visit_key=visit_key,
        talent=talent,
    )
    return {
        "audience": aud,
        "items": items,
        "pool_size": len(pool_for(aud)),
    }


def report_suggest_chips(
    talent: str | None,
    *,
    limit: int = 4,
    user_id: int | None = None,
    visit_key: str | None = None,
) -> list[dict[str, Any]]:
    """报告页专用：默认 4 条，格式 {q, hot}。"""
    return pick_suggest_prompts(
        "report",
        limit=limit,
        user_id=user_id,
        visit_key=visit_key,
        talent=talent,
    )


def pick_chips(
    audience: str = "student",
    *,
    limit: int = 3,
    user_id: int | None = None,
    visit_key: str | None = None,
    talent: str | None = None,
) -> list[SuggestChip]:
    """测试 / 内部用：返回 SuggestChip 列表。"""
    aud = _normalize_audience(audience)
    chips = pick_from_pool(
        pool_for(aud),
        limit=limit,
        seed_parts=(aud, user_id, visit_key),
    )
    t = (talent or "").strip()
    if not t:
        return list(chips)
    return [c.rendered(talent=t) for c in chips]
