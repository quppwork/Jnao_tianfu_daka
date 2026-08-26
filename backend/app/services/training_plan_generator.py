"""AI 每日训练报告 — Retrieve + 豆包为主；可选百炼 file_search 直答。"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion
from app.services.training_rag_query import build_training_rag_query
from app.services.training_service import get_yesterday_training_context

logger = get_logger("training.report")

REPORT_SYSTEM = """你是陪伴孩子的训练老师。用简单、温暖的话告诉孩子今天怎么练（2-4 句）。
说清楚：先练什么、再练什么、练完怎么打卡。不要用「主线」「训练块」「轮次」等技术词。"""

TRAINING_BAILIAN_INSTRUCTIONS = REPORT_SYSTEM


def _report_system_with_rag(rag_block: str) -> str:
    if not rag_block:
        return REPORT_SYSTEM
    return (
        f"{REPORT_SYSTEM}\n\n"
        "—— 训练视频知识库参考（仅作事实依据，用孩子能懂的话转述，勿整段背诵）——\n"
        f"{rag_block}\n"
        "—— 知识库结束 ——\n"
        "说明：知识库补充训练方法/示范要点；今日具体练哪些项仍以输入里的「今日训练」为准。"
    )


async def _gather_training_rag_block(
    *,
    talent_primary: str | None,
    lesson_title: str,
    item_titles: list[str] | None = None,
    yesterday_summary: str | None = None,
) -> str:
    from app.services.bailian import training_rag_query

    query = build_training_rag_query(
        talent_primary=talent_primary,
        lesson_title=lesson_title,
        item_titles=item_titles,
        yesterday_summary=yesterday_summary,
    )
    rag = await training_rag_query(query)
    if not rag or not rag.rag_block:
        return ""
    logger.info(
        "training rag retrieve nodes=%s sources=%s",
        rag.node_count,
        rag.sources[:3],
    )
    return rag.rag_block


async def _generate_with_doubao(
    context: str,
    *,
    rag_block: str = "",
) -> str | None:
    ai_text = await chat_completion(
        system_prompt=_report_system_with_rag(rag_block),
        user_message=context,
        max_tokens=180,
        timeout=12,
    )
    return ai_text.strip() if ai_text else None


async def generate_daily_report_text(
    db: Session,
    child_user_id: int,
    *,
    lesson_title: str,
    talent_primary: str | None,
    yesterday_summary: str | None = None,
    item_titles: list[str] | None = None,
) -> str:
    context = f"天赋：{talent_primary or '未知'}；今日训练：{lesson_title}"
    if item_titles:
        names = "、".join(t for t in item_titles if t)
        if names:
            context += f"；训练项：{names}"
    if yesterday_summary:
        context += f"；昨日：{yesterday_summary}"
    else:
        context += "；首次训练"

    from app.services.bailian import training_knowledge_reply
    from app.services.bailian.config import config_ready_for_generate, load_bailian_config

    cfg = load_bailian_config()
    rag_query = build_training_rag_query(
        talent_primary=talent_primary,
        lesson_title=lesson_title,
        item_titles=item_titles,
        yesterday_summary=yesterday_summary,
    )

    # 主链路：Retrieve 切片 → 豆包润色
    if cfg.rag_fallback_doubao and not cfg.rag_generate:
        rag_block = await _gather_training_rag_block(
            talent_primary=talent_primary,
            lesson_title=lesson_title,
            item_titles=item_titles,
            yesterday_summary=yesterday_summary,
        )
        primary = await _generate_with_doubao(context, rag_block=rag_block)
        if primary:
            logger.info(
                "training retrieve+doubao reply len=%s nodes=%s",
                len(primary),
                bool(rag_block),
            )
            return primary

    # 可选：百炼 file_search 直答（BAILIAN_RAG_GENERATE=1）
    if config_ready_for_generate(cfg):
        prompt = f"{context}\n\n请根据知识库中的训练示范与说明，给出今日训练指引。\n用户背景：{rag_query}"
        ai_text = await training_knowledge_reply(prompt, instructions=TRAINING_BAILIAN_INSTRUCTIONS)
        if ai_text:
            logger.info("training bailian direct reply len=%s", len(ai_text))
            return ai_text.strip()
        if cfg.rag_fallback_doubao:
            logger.info("training bailian failed, fallback retrieve+doubao uid=%s", child_user_id)
            rag_block = await _gather_training_rag_block(
                talent_primary=talent_primary,
                lesson_title=lesson_title,
                item_titles=item_titles,
                yesterday_summary=yesterday_summary,
            )
            fallback = await _generate_with_doubao(context, rag_block=rag_block)
            if fallback:
                return fallback
    elif cfg.rag_fallback_doubao:
        rag_block = await _gather_training_rag_block(
            talent_primary=talent_primary,
            lesson_title=lesson_title,
            item_titles=item_titles,
            yesterday_summary=yesterday_summary,
        )
        fallback = await _generate_with_doubao(context, rag_block=rag_block)
        if fallback:
            return fallback

    return f"今日请完成音频训练「{lesson_title}」，认真听完后打卡。"


async def ensure_plan_report(
    db: Session, child_user_id: int, plan_date: date | None = None, *, force: bool = False, skip_ai: bool = False
) -> dict:
    """获取今日方案，必要时用 AI 根据昨日打卡生成 report_text"""
    from app.services.training_day import is_new_day_ready, training_day_meta, training_now, get_training_day
    from app.services.training_service import TrainingError, get_today_plan

    if not is_new_day_ready():
        now = training_now()
        meta = training_day_meta(now)
        return {
            "plan_id": 0,
            "plan_date": get_training_day(now),
            "status": "transition",
            "report_text": "训练日切换中，约 5 分钟后开始新的一天",
            "content_index": 0,
            "planned_minutes": None,
            "items": [],
            "day_locked": False,
            "globally_cutoff": True,
            **meta,
        }

    try:
        plan_data = get_today_plan(db, child_user_id, plan_date)
    except TrainingError as e:
        if e.status_code == 503:
            now = training_now()
            meta = training_day_meta(now)
            return {
                "plan_id": 0,
                "plan_date": get_training_day(now),
                "status": "transition",
                "report_text": e.message,
                "content_index": 0,
                "planned_minutes": None,
                "items": [],
                "day_locked": False,
                "globally_cutoff": True,
                **meta,
            }
        raise
    if skip_ai:
        return plan_data
    if not plan_data.get("plan_id"):
        return plan_data

    from app.db.models import TrainingPlan

    plan = db.get(TrainingPlan, plan_data["plan_id"])
    if not plan:
        return plan_data

    from app.services.training_child_guide import is_technical_schedule_note

    needs_ai = force or not plan.report_text or is_technical_schedule_note(plan.report_text)
    if not needs_ai:
        return plan_data

    assessment = get_latest_assessment(db, child_user_id)
    lesson = plan.items[0].title if plan.items else "今日训练"
    item_titles = [it.title for it in plan.items if it.title]
    yesterday_summary = get_yesterday_training_context(db, child_user_id, plan_date)
    plan.report_text = await generate_daily_report_text(
        db,
        child_user_id,
        lesson_title=lesson or "今日训练",
        talent_primary=assessment.talent_primary if assessment else None,
        yesterday_summary=yesterday_summary,
        item_titles=item_titles,
    )
    db.commit()
    db.refresh(plan)
    plan_data["report_text"] = plan.report_text
    from app.services.training_service import invalidate_plan_cache
    invalidate_plan_cache(child_user_id, plan.plan_date)
    return plan_data
