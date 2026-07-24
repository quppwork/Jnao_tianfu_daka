"""学生情境卡片 — sense 层。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ChildUser, TrainingPlan, TrainingRecord


@dataclass
class TodayPlanSnapshot:
    exists: bool = False
    planned_minutes: int | None = None
    item_count: int = 0
    done_count: int = 0
    has_started: bool = False
    status: str | None = None


@dataclass
class GuideContext:
    """注入开场 / 对话的结构化情境（控制体积）。"""

    child_user_id: int
    training_day: str
    nickname: str = ""
    grade: str = ""
    talent: str = ""
    has_assessment: bool = False
    today: TodayPlanSnapshot = field(default_factory=TodayPlanSnapshot)
    days_since_last_checkin: int | None = None
    skill_tiers: dict[str, int] = field(default_factory=dict)
    situation: str | None = None
    next_action: str | None = None

    def to_prompt_block(self) -> str:
        lines = [
            f"训练日: {self.training_day}",
            f"昵称: {self.nickname or '同学'}",
            f"年级: {self.grade or '未知'}",
            f"已测评: {'是' if self.has_assessment else '否'}",
            f"天赋: {self.talent or '无'}",
        ]
        if self.today.exists:
            lines.append(
                f"今日方案: 时长={self.today.planned_minutes}min "
                f"项={self.today.done_count}/{self.today.item_count} "
                f"已开始={'是' if self.today.has_started else '否'} "
                f"status={self.today.status}"
            )
        else:
            lines.append("今日方案: 无")
        if self.days_since_last_checkin is not None:
            lines.append(f"距上次打卡: {self.days_since_last_checkin} 天")
        if self.skill_tiers:
            items = list(self.skill_tiers.items())[:8]
            tier_s = ", ".join(f"{k}={v}" for k, v in items)
            lines.append(f"技能Tier: {tier_s}")
        if self.situation:
            lines.append(
                f"判定情境: {self.situation} → 建议动作: {self.next_action}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_guide_context(db: Session, child_user_id: int) -> GuideContext:
    """从 DB 组装情境卡片。"""
    from app.services.assessment_service import resolve_effective_talent
    from app.services.child_training_state import get_training_progress
    from app.services.dev_clock import resolve_training_now
    from app.services.training_day import get_training_day
    from app.services.training_schedule_service import _plan_has_started

    now = resolve_training_now(db, child_user_id)
    day = get_training_day(now)
    ctx = GuideContext(
        child_user_id=child_user_id,
        training_day=day.isoformat(),
    )

    child = db.get(ChildUser, child_user_id)
    if child:
        ctx.nickname = (child.nickname or "").strip()
        pj = child.profile_json if isinstance(child.profile_json, dict) else {}
        ctx.grade = str(
            pj.get("grade")
            or (pj.get("learner") or {}).get("grade")
            or ""
        )
        td = pj.get("talent_display") or pj.get("talent_primary") or ""
        if td:
            ctx.talent = str(td)

    talent = resolve_effective_talent(db, child_user_id)
    if talent and talent.get("has_assessment"):
        ctx.has_assessment = True
        ctx.talent = (
            talent.get("talent_primary")
            or talent.get("talent_tag")
            or ctx.talent
            or ""
        )
    elif talent and talent.get("talent_code"):
        # 引导自选也视为可训练
        ctx.has_assessment = True
        ctx.talent = talent.get("talent_primary") or ctx.talent or ""

    plan = db.scalar(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.items))
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date == day,
        )
    )
    if plan:
        items = list(plan.items or [])
        done = sum(1 for it in items if (it.checkin_status or "") == "done")
        ctx.today = TodayPlanSnapshot(
            exists=True,
            planned_minutes=plan.planned_minutes,
            item_count=len(items),
            done_count=done,
            has_started=_plan_has_started(db, plan),
            status=plan.status,
        )

    last_date = db.scalar(
        select(func.max(TrainingRecord.train_date)).where(
            TrainingRecord.child_user_id == child_user_id
        )
    )
    if isinstance(last_date, date):
        ctx.days_since_last_checkin = (day - last_date).days

    if child:
        state = get_training_progress(child)
        skills = state.get("skills") or {}
        ctx.skill_tiers = {
            sk: int(sd.get("tier") or 1)
            for sk, sd in skills.items()
            if isinstance(sd, dict)
        }

    return ctx
