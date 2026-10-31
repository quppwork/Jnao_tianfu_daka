"""知识库选源策略 — 当前阶段只启用一个百炼库。

默认：talent_doc（index_id=ockqxuuru1，控制台「Jnao软件知识库」）。
知识问答应用：BAILIAN_KB_QA_AID（控制台「知识问答」已发布 aid）。
恢复双库：KB_SINGLE_SOURCE=0，并保证 video_practice 配置可用。
"""

from __future__ import annotations

import os

# 与 kb_registry.yaml 中 talent_doc.index_id 对齐
DEFAULT_ACTIVE_SOURCE_KEY = "talent_doc"
DEFAULT_ACTIVE_INDEX_ID = "ockqxuuru1"
# 控制台：Jnao软件知识库_知识问答（已发布）
DEFAULT_KB_QA_AID = "aid-9eca891478184a39a7e0d37419919ae9"


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


def knowledge_qa_aid() -> str:
    """首页引导 / 家长引导 / 报告天赋解答共用的知识问答 aid。"""
    env = (os.getenv("BAILIAN_KB_QA_AID") or os.getenv("BAILIAN_KB_QA_DOC_AID") or "").strip()
    if env:
        return env
    try:
        from app.services.kb_registry import load_kb_registry

        src = load_kb_registry().get(active_kb_source_key())
        aid = str(getattr(src, "aid", "") or "").strip()
        if aid:
            return aid
    except Exception:
        pass
    return DEFAULT_KB_QA_AID
