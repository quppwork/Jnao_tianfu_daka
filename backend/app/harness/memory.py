"""截断 / 折叠 — 内核入口；存储仍分 Guide / QA / Consult 各表。"""

from __future__ import annotations

from typing import Any

from app.agents.memory_policy import (
    HISTORY_KEEP_DEFAULT,
    MAX_DIGEST_CHARS,
    digest_prompt_block,
    fold_overflow_history,
)


def truncate_history(messages: list[dict], *, max_turns: int = 12) -> list[dict]:
    if max_turns <= 0 or len(messages) <= max_turns:
        return list(messages or [])
    return list(messages[-max_turns:])


def fold_and_truncate(
    messages: list[dict],
    mem: dict[str, Any] | None = None,
    *,
    keep: int = HISTORY_KEEP_DEFAULT,
    max_digest_chars: int = MAX_DIGEST_CHARS,
) -> tuple[list[dict], dict[str, Any]]:
    recent, out_mem = fold_overflow_history(
        list(messages or []),
        mem or {},
        keep=keep,
        max_digest_chars=max_digest_chars,
    )
    return truncate_history(recent, max_turns=keep), out_mem


def window_for_model(
    messages: list[dict],
    mem: dict[str, Any] | None = None,
    *,
    keep: int = HISTORY_KEEP_DEFAULT,
) -> tuple[list[dict], dict[str, Any]]:
    """给模型的上下文窗：system 常驻，其余折叠；不改原 messages。

    keep 默认与 memory_policy.HISTORY_KEEP_DEFAULT 一致，避免门面已折一轮、
    内核再用不同窗口二次压扁。
    """
    msgs = list(messages or [])
    systems = [m for m in msgs if m.get("role") == "system"]
    rest = [m for m in msgs if m.get("role") != "system"]
    recent, out_mem = fold_and_truncate(rest, mem, keep=keep)
    digest = digest_prompt_block(out_mem)
    out_sys = [dict(m) for m in systems]
    if digest:
        if out_sys:
            head = dict(out_sys[0])
            body = str(head.get("content") or "").rstrip()
            if digest not in body:
                head["content"] = f"{body}\n\n{digest}"
            out_sys[0] = head
        else:
            out_sys = [{"role": "system", "content": digest}]
    return out_sys + recent, out_mem


__all__ = [
    "HISTORY_KEEP_DEFAULT",
    "MAX_DIGEST_CHARS",
    "digest_prompt_block",
    "fold_and_truncate",
    "fold_overflow_history",
    "truncate_history",
    "window_for_model",
]
