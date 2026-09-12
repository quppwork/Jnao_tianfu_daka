"""知识库选源策略 — 当前阶段只启用一个百炼库。

默认：talent_doc（index_id=x1micrdmjq）。
恢复双库：KB_SINGLE_SOURCE=0，并保证 video_practice 配置可用。
"""

from __future__ import annotations

import os

# 与 kb_registry.yaml 中 talent_doc.index_id 对齐
DEFAULT_ACTIVE_SOURCE_KEY = "talent_doc"
DEFAULT_ACTIVE_INDEX_ID = "x1micrdmjq"


def kb_single_source() -> bool:
    return (os.getenv("KB_SINGLE_SOURCE") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def active_kb_source_key() -> str:
    key = (os.getenv("KB_ACTIVE_SOURCE_KEY") or DEFAULT_ACTIVE_SOURCE_KEY).strip()
    return key or DEFAULT_ACTIVE_SOURCE_KEY
