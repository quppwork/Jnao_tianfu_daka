"""按业务隔离的提问池 — 报告 / 孩子引导 / 家长引导 互不混用。"""

from __future__ import annotations

from app.suggest_prompts.pools.guide_child import GUIDE_CHILD_POOL
from app.suggest_prompts.pools.guide_parent import GUIDE_PARENT_POOL
from app.suggest_prompts.pools.report_talent import REPORT_TALENT_POOL
from app.suggest_prompts.types import SuggestAudience, SuggestChip

# 答疑兼容旧 audience=qa（练法向短池）
_QA_POOL: tuple[SuggestChip, ...] = tuple(
    c
    for c in GUIDE_CHILD_POOL
    if any(k in c.text for k in ("怎么练", "开口窍", "超脑", "提分营", "扫描", "影像", "极速"))
)


def pool_for(audience: SuggestAudience | str) -> tuple[SuggestChip, ...]:
    if audience == "report":
        return REPORT_TALENT_POOL
    if audience == "parent":
        return GUIDE_PARENT_POOL
    if audience == "qa":
        return _QA_POOL or GUIDE_CHILD_POOL[:12]
    return GUIDE_CHILD_POOL
