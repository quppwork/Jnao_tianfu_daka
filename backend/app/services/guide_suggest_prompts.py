"""兼容入口 — 实现已迁至 app.suggest_prompts（按业务分池）。

API / 旧 import 仍走本模块；新代码请直接 `from app.suggest_prompts import ...`。
"""

from __future__ import annotations

from app.suggest_prompts.pools.guide_child import GUIDE_CHILD_POOL
from app.suggest_prompts.pools.guide_parent import GUIDE_PARENT_POOL
from app.suggest_prompts.service import pick_suggest_prompts, suggest_prompts_payload

# 测试兼容：旧名指向孩子引导池文案列表
_KB_DOC_PROMPTS = [c.as_guide_item() for c in GUIDE_CHILD_POOL]


def _pool_for(audience: str) -> list[dict[str, str]]:
    if audience == "parent":
        return [c.as_guide_item() for c in GUIDE_PARENT_POOL]
    return [c.as_guide_item() for c in GUIDE_CHILD_POOL]


__all__ = [
    "pick_suggest_prompts",
    "suggest_prompts_payload",
    "_KB_DOC_PROMPTS",
    "_pool_for",
]
