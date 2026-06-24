"""AI 每日训练报告生成"""

from sqlalchemy.orm import Session

from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion
from app.services.training_service import get_or_create_today_plan

REPORT_SYSTEM = """你是 JNAO 天赋成长平台的训练教练。
根据学员天赋和今日训练内容，生成「今日训练报告」。
要求：极简，2-4 句话，像给孩子的今日指令，温暖亲切，不要废话。"""


async def generate_daily_report_text(
    db: Session,
    child_user_id: int,
    *,
    lesson_title: str,
    talent_primary: str | None,
    yesterday_summary: str | None = None,
) -> str:
    context = f"学员天赋：{talent_primary or '未知'}\n今日训练：{lesson_title}"
    if yesterday_summary:
        context += f"\n昨日情况：{yesterday_summary}"

    ai_text = await chat_completion(system_prompt=REPORT_SYSTEM, user_message=context)
    if ai_text:
        return ai_text.strip()
    return f"今日请完成音频训练「{lesson_title}」，认真听完后打卡。"


async def ensure_plan_report(db: Session, child_user_id: int) -> dict:
    """获取今日方案，必要时用 AI 补充 report_text"""
    plan_data = get_or_create_today_plan(db, child_user_id)
    from app.db.models import TrainingPlan

    plan = db.get(TrainingPlan, plan_data["plan_id"])
    if not plan:
        return plan_data

    if plan.report_text and not plan.report_text.startswith("今日音频："):
        return plan_data

    assessment = get_latest_assessment(db, child_user_id)
    lesson = plan.items[0].title if plan.items else "今日训练"
    plan.report_text = await generate_daily_report_text(
        db,
        child_user_id,
        lesson_title=lesson or "今日训练",
        talent_primary=assessment.talent_primary if assessment else None,
    )
    db.commit()
    db.refresh(plan)
    plan_data["report_text"] = plan.report_text
    return plan_data
