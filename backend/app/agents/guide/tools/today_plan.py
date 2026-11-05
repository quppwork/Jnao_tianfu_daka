"""工具：今日训练摘要（只读，不触发排课写库）。

仅返回有无方案、计划时长、完成计数等摘要，不展开各项课件/排课明细，
避免对话侧被用来反推训练逻辑。
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.agents.guide.tools import register


@register("get_today_plan")
def get_today_plan(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    from app.agents.guide.context import build_guide_context

    ctx = build_guide_context(db, child_user_id)
    return {
        "training_day": ctx.training_day,
        "today": asdict(ctx.today),
    }
