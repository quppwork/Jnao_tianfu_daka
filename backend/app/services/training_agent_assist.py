"""训练 Agent 辅助排课门面 — 调 agents/training_schedule 工具循环，再校验投影。

禁止：直接写 DB / 改 Tier / OSS / 代打卡。
失败码用于结构化日志与 schedule_mode=agent_fallback。
"""

from __future__ import annotations

import asyncio
import os
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from config.loader import load_training_curriculum
from app.services.training_formula_engine import ELECTIVE_SKILLS
from app.core.logger import get_logger

logger = get_logger("training.schedule.assist")


class AssistFail(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}" if message else code)


def schedule_assist_config() -> dict[str, Any]:
    """YAML + 环境变量。TRAINING_AGENT_SCHEDULE=1/0 优先于 yaml schedule_assist。"""
    cfg = (load_training_curriculum().get("llm_routing") or {}) if load_training_curriculum() else {}
    env = os.getenv("TRAINING_AGENT_SCHEDULE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        enabled = True
    elif env in ("0", "false", "no", "off"):
        enabled = False
    else:
        enabled = bool(cfg.get("schedule_assist", False))
    timeout = float(
        os.getenv(
            "TRAINING_AGENT_SCHEDULE_TIMEOUT",
            str(cfg.get("schedule_timeout_sec", 600)),
        )
    )
    timeout = max(3.0, min(timeout, 600.0))
    return {
        "enabled": enabled,
        "timeout_sec": timeout,
        "provider": cfg.get("provider") or "doubao",
    }


def is_schedule_assist_enabled() -> bool:
    return bool(schedule_assist_config()["enabled"])


def validate_and_project(
    draft_skills: list[str],
    *,
    available_skills: list[str],
    rule_slots: list[str],
    pad_priority: list[str] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Agent 技能顺序意图 → 对齐槽位预算 N；选修尾随保留规则结果。

    补齐顺序（意图优先）：
      1) 保留草案（可含重复）
      2) 按 pad_priority（弱项→重点→可排）循环补足
      3) 仍不足时才用 rule_slots 多重集 / 循环垫底

    返回 (projected_slots, meta)。
    """
    available = set(available_skills)
    elective = set(ELECTIVE_SKILLS)
    elective |= set(((load_training_curriculum() or {}).get("skills") or {}).get("elective") or [])

    required_target = [s for s in rule_slots if s not in elective]
    elective_tail = [s for s in rule_slots if s in elective]
    target_n = len(required_target)
    if target_n <= 0:
        raise AssistFail("no_rule_slots", "规则槽位为空")

    cleaned: list[str] = []
    dropped_invalid: list[str] = []
    for name in draft_skills:
        if name in elective:
            dropped_invalid.append(name)
            continue
        if name not in available:
            dropped_invalid.append(name)
            continue
        cleaned.append(name)

    if not cleaned:
        raise AssistFail("no_valid_skills", "草案技能均不在可用集合")

    dropped_for_slot_cap = cleaned[target_n:]
    projected = cleaned[:target_n]
    padded_from_intent: list[str] = []
    padded_from_rule: list[str] = []

    if len(projected) < target_n:
        priority = [
            s
            for s in (pad_priority or [])
            if s in available and s not in elective
        ]
        i = 0
        safety = target_n * 4
        while len(projected) < target_n and priority and i < safety:
            s = priority[i % len(priority)]
            projected.append(s)
            padded_from_intent.append(s)
            i += 1

    if len(projected) < target_n:
        need_counts = Counter(required_target)
        have_counts = Counter(projected)
        for s in required_target:
            if len(projected) >= target_n:
                break
            if have_counts[s] < need_counts[s]:
                projected.append(s)
                have_counts[s] += 1
                padded_from_rule.append(s)
        i = 0
        while len(projected) < target_n and required_target:
            s = required_target[i % len(required_target)]
            projected.append(s)
            padded_from_rule.append(s)
            i += 1

    if len(projected) != target_n:
        raise AssistFail("project_len", f"投影长度 {len(projected)} != {target_n}")

    final = projected + elective_tail
    meta = {
        "target_n": target_n,
        "draft_len": len(draft_skills),
        "cleaned_len": len(cleaned),
        "dropped_invalid": dropped_invalid,
        "dropped_for_slot_cap": dropped_for_slot_cap,
        "padded_from_intent": padded_from_intent,
        "padded_from_rule": padded_from_rule,
        # 兼容旧字段：合并两类补齐
        "padded_from_priority": padded_from_intent + padded_from_rule,
    }
    return final, meta


async def propose_projected_slots(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """跑排课 Agent 工具循环 → 校验投影。成功返回 (slots, meta)。"""
    from app.agents.training_schedule.runner import (
        ScheduleAssistError,
        run_schedule_assist,
    )

    cfg = schedule_assist_config()
    if not cfg["enabled"]:
        raise AssistFail("disabled", "辅助排课未开启")

    timeout = float(cfg["timeout_sec"])
    try:
        result = await asyncio.wait_for(
            run_schedule_assist(
                db,
                child_user_id,
                planned_minutes,
                plan_date=plan_date,
                timeout_sec=timeout,
            ),
            timeout=timeout + 2.0,
        )
    except asyncio.TimeoutError as e:
        raise AssistFail("timeout", f"超时 {timeout}s") from e
    except ScheduleAssistError as e:
        raise AssistFail(e.code, e.message) from e

    draft = list(result.get("draft") or [])
    reason = result.get("reason")
    if reason is not None:
        reason = str(reason).strip() or None
        if reason and len(reason) > 500:
            reason = reason[:500]
    available = list(result.get("available_skills") or [])
    rule_slots = list(result.get("rule_slots") or [])
    pad_priority = list(result.get("pad_priority") or [])
    projected, project_meta = validate_and_project(
        draft,
        available_skills=available,
        rule_slots=rule_slots,
        pad_priority=pad_priority,
    )
    meta = {
        "mode": "agent",
        "reason": reason,
        "draft": draft,
        "projected": projected,
        "rule_slots": rule_slots,
        "pad_priority": pad_priority,
        "rule_strategy": result.get("rule_strategy"),
        "tools_used": [
            {"name": t.get("name"), "ok": t.get("ok")}
            for t in (result.get("tools_used") or [])
            if isinstance(t, dict)
        ],
        "timeout_sec": timeout,
        "path": "training_schedule_agent",
        **project_meta,
    }
    logger.info(
        "training_schedule_assist tools=%s draft=%s projected=%s target_n=%s "
        "padded_intent=%s padded_rule=%s dropped_cap=%s reason=%s",
        [t.get("name") for t in meta["tools_used"]],
        draft,
        projected,
        meta.get("target_n"),
        meta.get("padded_from_intent"),
        meta.get("padded_from_rule"),
        meta.get("dropped_for_slot_cap"),
        (reason or "")[:80],
    )
    return projected, meta
