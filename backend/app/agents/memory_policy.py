"""对话记忆统一策略 — 引导 / 答疑共用折叠与 token 预算约定。

存储仍分域：
- 引导：profile_json.guide_memory（跨会话学生记忆）
- 答疑：qa_session.meta_json rolling_summary（随会话删清）

本模块只统一「怎么压历史、摘要多长、进 prompt 的标签」。

写入时机约定：
1. 生成前（必写）：fold 溢出 +（引导）抽取用户意向 → save；答疑仅在
   rolling_summary 变化时 save_session_memory。
2. 助手正文：进会话消息表，不回灌进 digest（避免双写膨胀）。
3. 显式画像写入：仅引导 writes 确认卡白名单，确认后落库。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ── 预算（改这里即可同时影响 guide / qa）──
MAX_DIGEST_CHARS = 600
HISTORY_KEEP_DEFAULT = 10
HISTORY_LOAD_DEFAULT = 40
GUIDE_HISTORY_KEEP_DEFAULT = 12  # 引导略多保留几轮短问答


def fold_overflow_history(
    messages: list[dict],
    mem: dict[str, Any],
    *,
    keep: int = HISTORY_KEEP_DEFAULT,
    max_digest_chars: int = MAX_DIGEST_CHARS,
    empty_mem_factory: Any | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """超出 keep 的旧轮次压进 rolling_summary，返回尾部历史 + 更新后的 mem。"""
    msgs = list(messages or [])
    if empty_mem_factory is not None and not mem:
        out_mem = empty_mem_factory()
    else:
        out_mem = deepcopy(mem) if mem else {"rolling_summary": ""}
    if keep <= 0 or len(msgs) <= keep:
        return msgs, out_mem
    older = msgs[:-keep]
    recent = msgs[-keep:]
    lines: list[str] = []
    for m in older:
        role = "学员" if m.get("role") == "user" else "老师"
        c = str(m.get("content") or "").strip().replace("\n", " ")
        if c:
            lines.append(f"{role}:{c[:80]}")
    chunk = "；".join(lines)
    prev = str(out_mem.get("rolling_summary") or "").strip()
    merged = f"{prev}；{chunk}".strip("；") if prev else chunk
    if len(merged) > max_digest_chars:
        merged = "…" + merged[-(max_digest_chars - 1) :]
    out_mem["rolling_summary"] = merged
    return recent, out_mem


def digest_prompt_block(
    mem: dict[str, Any] | None,
    *,
    label: str = "近期对话摘要",
) -> str:
    if not mem:
        return ""
    digest = str(mem.get("rolling_summary") or "").strip()
    if not digest:
        return ""
    return f"{label}: {digest}"
