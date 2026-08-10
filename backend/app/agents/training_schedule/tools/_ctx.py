"""排课工具共享请求上下文（由 runner 注入，工具只读）。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date

from app.services.training_formula_engine import HistoryEntry


@dataclass
class ScheduleRequestCtx:
    planned_minutes: int
    plan_date: date | None = None
    overall_tier: int = 1
    grade: str = ""
    grade_band: str = "primary_low"
    skill_tiers: dict[str, int] = field(default_factory=dict)
    history: tuple[HistoryEntry, ...] = ()
    talent_tag: str | None = None
    talent_code: int | None = None
    training_days: int = 0
    available_skills: list[str] = field(default_factory=list)  # selectable_now
    rule_slots: list[str] = field(default_factory=list)
    rule_strategy: str | None = None
    target_slot_count: int = 0
    # 投影补齐优先级（struggling → key → …）；不对 LLM 展示规则名单
    pad_priority: list[str] = field(default_factory=list)
    # propose_skill_draft 写入
    draft_skills: list[str] | None = None
    draft_reason: str | None = None
    draft_submitted: bool = False


_REQUEST: ContextVar[ScheduleRequestCtx | None] = ContextVar(
    "training_schedule_request", default=None
)


def set_request_ctx(ctx: ScheduleRequestCtx) -> None:
    _REQUEST.set(ctx)


def get_request_ctx() -> ScheduleRequestCtx:
    ctx = _REQUEST.get()
    if ctx is None:
        raise RuntimeError("schedule request ctx not set")
    return ctx


def clear_request_ctx() -> None:
    _REQUEST.set(None)
