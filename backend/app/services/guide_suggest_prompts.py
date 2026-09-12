"""进页提问引导 — 入库知识库文档主题 → 可点 chips。

不调用 LLM / 百炼：curated（已入库可答）+ kb_registry.tags，毫秒级。
每次 visit_key 不同则随机换一批；家长/学生共用知识库文档问法池。
"""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any, Literal

from app.services.kb_registry import get_kb_registry

Audience = Literal["student", "parent", "qa"]

# 已入库、可答的知识库文档问法（学生/家长共用主池）
_KB_DOC_PROMPTS: list[dict[str, str]] = [
    {"label": "学者天赋是什么", "text": "学者天赋是什么"},
    {"label": "思者天赋是什么", "text": "思者天赋是什么"},
    {"label": "行者天赋是什么", "text": "行者天赋是什么"},
    {"label": "德者天赋是什么", "text": "德者天赋是什么"},
    {"label": "赢者天赋是什么", "text": "赢者天赋是什么"},
    {"label": "什么是天赋", "text": "什么是天赋"},
    {"label": "五者天赋怎么分", "text": "五者天赋是怎么划分的"},
    {"label": "什么是火箭提分营", "text": "什么是火箭提分营"},
    {"label": "提分营适合谁", "text": "火箭提分营适合什么样的孩子"},
    {"label": "提分营怎么收费", "text": "火箭提分营的服务周期和收费是怎样的"},
    {"label": "超脑阅读怎么练", "text": "超脑阅读怎么练"},
    {"label": "开口窍是什么", "text": "开口窍是什么"},
    {"label": "影像追忆怎么练", "text": "影像追忆怎么练"},
    {"label": "扫描速记要点", "text": "扫描速记的训练要点是什么"},
    {"label": "极速运算怎么练", "text": "极速运算怎么练"},
    {"label": "家长课堂是什么", "text": "家长课堂是什么，有哪些课"},
    {"label": "报告怎么解读", "text": "天赋报告该怎么解读"},
]

# 答疑侧重练法
_QA_PROMPTS: list[dict[str, str]] = [
    {"label": "超脑阅读怎么练", "text": "超脑阅读怎么练"},
    {"label": "开口窍练法", "text": "开口窍怎么练"},
    {"label": "极速运算方法", "text": "极速运算怎么练才有效"},
    {"label": "影像追忆步骤", "text": "影像追忆的练习步骤是什么"},
    {"label": "扫描速记要点", "text": "扫描速记的要点有哪些"},
    {"label": "学者怎么学语文", "text": "学者天赋学语文有什么方法"},
    {"label": "思者怎么学数学", "text": "思者天赋学数学怎么提升"},
    {"label": "什么是火箭提分营", "text": "什么是火箭提分营"},
]

# registry tag → 更自然的问法
_TAG_ALIASES: dict[str, dict[str, str]] = {
    "学者": {"label": "学者天赋是什么", "text": "学者天赋是什么"},
    "思者": {"label": "思者天赋是什么", "text": "思者天赋是什么"},
    "行者": {"label": "行者天赋是什么", "text": "行者天赋是什么"},
    "德者": {"label": "德者天赋是什么", "text": "德者天赋是什么"},
    "赢者": {"label": "赢者天赋是什么", "text": "赢者天赋是什么"},
    "五者": {"label": "五者天赋怎么分", "text": "五者天赋是怎么划分的"},
    "天赋": {"label": "什么是天赋", "text": "什么是天赋"},
    "火箭提分营": {"label": "什么是火箭提分营", "text": "什么是火箭提分营"},
    "提分营": {"label": "提分营适合谁", "text": "火箭提分营适合什么样的孩子"},
    "开口窍": {"label": "开口窍是什么", "text": "开口窍是什么"},
    "开口穹": {"label": "开口窍是什么", "text": "开口窍是什么"},
    "超脑阅读": {"label": "超脑阅读怎么练", "text": "超脑阅读怎么练"},
    "影像追忆": {"label": "影像追忆怎么练", "text": "影像追忆怎么练"},
    "扫描速记": {"label": "扫描速记要点", "text": "扫描速记的训练要点是什么"},
    "极速运算": {"label": "极速运算怎么练", "text": "极速运算怎么练"},
    "家长课堂": {"label": "家长课堂是什么", "text": "家长课堂是什么，有哪些课"},
    "家长课程": {"label": "家长课堂是什么", "text": "家长课堂是什么，有哪些课"},
}

_AUTO_SKIP = {
    "练法", "怎么练", "如何练", "视频示范", "训练方法", "示范视频",
    "产品", "课程", "适合谁", "营期", "收费", "平台说明", "学习规律",
    "系统训练", "单点刷题", "年级要求", "晋级", "报告解读", "感知力",
    "多元感知", "极速学习", "视频示范",
}


def _auto_from_registry() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        reg = get_kb_registry()
    except Exception:
        return out
    for src in reg.sources:
        for tag in src.tags or []:
            t = str(tag).strip()
            if not t or t in _AUTO_SKIP or t in seen:
                continue
            if t in _TAG_ALIASES:
                item = dict(_TAG_ALIASES[t])
                if item["text"] in seen:
                    continue
                seen.add(t)
                seen.add(item["text"])
                out.append(item)
                continue
            if len(t) < 2 or t.endswith("怎么练") or t.startswith("怎么"):
                continue
            seen.add(t)
            label = f"什么是{t}" if not t.startswith("什么") else t
            text = label
            if text in seen:
                continue
            seen.add(text)
            out.append({"label": label[:16], "text": text})
    return out


def _pool_for(audience: Audience) -> list[dict[str, str]]:
    if audience == "qa":
        base = list(_QA_PROMPTS)
    else:
        # 学生 / 家长：同一套入库文档问法
        base = list(_KB_DOC_PROMPTS)
    have = {c["text"] for c in base}
    for item in _auto_from_registry():
        if item["text"] not in have:
            base.append(item)
            have.add(item["text"])
    return base


def _seed_int(*parts: Any) -> int:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return int(hashlib.md5(raw.encode("utf-8")).hexdigest()[:8], 16)


def pick_suggest_prompts(
    audience: str = "student",
    *,
    limit: int = 3,
    user_id: int | None = None,
    visit_key: str | None = None,
) -> list[dict[str, str]]:
    """返回本轮展示的提问 chips。visit_key 每次不同 → 随机换一批。"""
    aud: Audience = audience if audience in ("student", "parent", "qa") else "student"
    limit = max(1, min(int(limit or 3), 8))
    pool = _pool_for(aud)
    if not pool:
        return []
    # 无 visit_key 时真随机，避免同分钟内重复
    vk = visit_key or secrets.token_hex(8)
    rng = random.Random(_seed_int(aud, user_id, vk))
    picked = pool[:]
    rng.shuffle(picked)
    return picked[:limit]


def suggest_prompts_payload(
    audience: str = "student",
    *,
    limit: int = 3,
    user_id: int | None = None,
    visit_key: str | None = None,
) -> dict[str, Any]:
    items = pick_suggest_prompts(
        audience, limit=limit, user_id=user_id, visit_key=visit_key
    )
    return {"audience": audience, "items": items}
