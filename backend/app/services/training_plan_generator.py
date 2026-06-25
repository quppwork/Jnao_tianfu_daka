"""AI 每日训练报告生成 — 结合天赋、昨日打卡与今日推送音频"""

from datetime import date

from sqlalchemy.orm import Session

from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion
from app.services.training_service import get_or_create_today_plan, get_yesterday_training_context

REPORT_SYSTEM = """你是 JNAO 天赋成长平台的训练教练。
根据学员天赋类型、昨日训练打卡情况、今日推送音频，生成「今日训练方案」文字。
要求：
1. 极简 2-4 句话，像给孩子的今日指令，温暖亲切
2. 若有昨日打卡信息，简要承接（如配合度低则鼓励，完成得好则表扬）
3. 明确今日要先听音频、再做能力训练打卡
4. 不要废话，不要 markdown 列表"""


async def generate_daily_report_text(
    db: Session,
    child_user_id: int,
    *,
    lesson_title: str,
    talent_primary: str | None,
    yesterday_summary: str | None = None,
) -> str:
    context = f"学员天赋：{talent_primary or '未知'}\n今日推送音频：{lesson_title}"
    if yesterday_summary:
        context += f"\n昨日训练与打卡：{yesterday_summary}"
    else:
        context += "\n昨日训练与打卡：首次训练，无历史记录"

    ai_text = await chat_completion(system_prompt=REPORT_SYSTEM, user_message=context)
    if ai_text:
        return ai_text.strip()
    return f"今日请完成音频训练「{lesson_title}」，认真听完后打卡。"


async def ensure_plan_report(
    db: Session, child_user_id: int, plan_date: date | None = None, *, force: bool = False
) -> dict:
    """获取今日方案，必要时用 AI 根据昨日打卡生成 report_text"""
    plan_data = get_or_create_today_plan(db, child_user_id, plan_date)
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
