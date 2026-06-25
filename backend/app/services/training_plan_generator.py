"""AI 每日训练报告生成 — 结合天赋、昨日打卡与今日推送音频"""

from datetime import date

from sqlalchemy.orm import Session

from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion
from app.services.training_service import get_or_create_today_plan, get_yesterday_training_context

REPORT_SYSTEM = """你是 JNAO 训练教练。根据天赋、昨日打卡、今日音频，写 2-3 句今日指令，温暖简短，无 markdown。"""


async def generate_daily_report_text(
    db: Session,
    child_user_id: int,
    *,
    lesson_title: str,
    talent_primary: str | None,
    yesterday_summary: str | None = None,
) -> str:
    context = f"天赋：{talent_primary or '未知'}；今日音频：{lesson_title}"
    if yesterday_summary:
        context += f"；昨日：{yesterday_summary}"
    else:
        context += "；首次训练"

    ai_text = await chat_completion(
        system_prompt=REPORT_SYSTEM,
        user_message=context,
        max_tokens=180,
        timeout=12,
    )
    if ai_text:
        return ai_text.strip()
    return f"今日请完成音频训练「{lesson_title}」，认真听完后打卡。"


async def ensure_plan_report(
    db: Session, child_user_id: int, plan_date: date | None = None, *, force: bool = False, skip_ai: bool = False
) -> dict:
    """获取今日方案，必要时用 AI 根据昨日打卡生成 report_text"""
    plan_data = get_or_create_today_plan(db, child_user_id, plan_date)
    if skip_ai:
        return plan_data

    from app.db.models import TrainingPlan

    plan = db.get(TrainingPlan, plan_data["plan_id"])
    if not plan:
        return plan_data

    needs_ai = force or not plan.report_text or plan.report_text.startswith("今日音频：")
    if not needs_ai:
        return plan_data

    assessment = get_latest_assessment(db, child_user_id)
    lesson = plan.items[0].title if plan.items else "今日训练"
    yesterday_summary = get_yesterday_training_context(db, child_user_id, plan_date)
    plan.report_text = await generate_daily_report_text(
        db,
        child_user_id,
        lesson_title=lesson or "今日训练",
        talent_primary=assessment.talent_primary if assessment else None,
        yesterday_summary=yesterday_summary,
    )
    db.commit()
    db.refresh(plan)
    plan_data["report_text"] = plan.report_text
    return plan_data
