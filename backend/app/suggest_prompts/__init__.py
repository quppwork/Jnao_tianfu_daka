"""用户提问引导 chips — 按业务分池、轮换展示。

目录：
  types.py / rotate.py / service.py
  pools/report_talent.py   报告 20 条
  pools/guide_child.py     孩子引导 30 条
  pools/guide_parent.py    家长引导 30 条
"""

from app.suggest_prompts.service import (
    pick_suggest_prompts,
    report_suggest_chips,
    suggest_prompts_payload,
)
from app.suggest_prompts.types import SuggestAudience, SuggestChip

__all__ = [
    "SuggestAudience",
    "SuggestChip",
    "pick_suggest_prompts",
    "report_suggest_chips",
    "suggest_prompts_payload",
]
