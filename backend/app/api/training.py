"""今日训练 API — 方案、打卡、时段"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.schemas.training import (
    CheckinDeleteResponse,
    CheckinHistoryResponse,
    CheckinRecordOut,
    CheckinRequest,
    CheckinResponse,
    CheckinUpdateRequest,
    ScheduleRequest,
    OptionalChoiceRequest,
    TalentVideoResponse,
    TrainingEntryResponse,
    TrainingProgressResponse,
    TrainingTodayResponse,
    WatchProgressRequest,
    WatchProgressResponse,
    WindowResponse,
    WindowSetRequest,
    WindowStatusResponse,
)
from app.services import training_service
from app.services.assessment_service import effective_talent_code, get_latest_assessment, has_valid_talent
from app.services.training_optional_service import accept_optional_training, decline_optional_training
from app.services.training_plan_generator import ensure_plan_report
from app.services.training_schedule_service import schedule_training_by_duration
from app.services.training_service import TrainingError
from app.services.video_push_service import get_talent_training_video

router = APIRouter(prefix="/api/training", tags=["training"])


@router.post("/schedule", response_model=TrainingTodayResponse)
async def schedule_training(
    req: ScheduleRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    """按今日训练时长排课：豆包路由 A/B 音频 + 天赋固定视频"""
    try:
        return await schedule_training_by_duration(
            db, child_user_id, req.planned_minutes, plan_date=plan_date
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/schedule/optional", response_model=TrainingTodayResponse)
def schedule_optional_training(
    req: OptionalChoiceRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    """孩子确认是否练习可选训练项（如高效作业），按天赋权重推荐"""
    try:
        if req.accept:
            return accept_optional_training(
                db, child_user_id, req.skill, plan_date=plan_date
            )
        return decline_optional_training(
            db, child_user_id, req.skill, plan_date=plan_date
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/video/talent", response_model=TalentVideoResponse)
def talent_training_video(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    """按天赋返回固定训练视频（支持测评结果或引导页自选天赋）"""
    from app.services.training_service import _resolve_effective_talent

    talent = _resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise HTTPException(403, "请先完成天赋测评或选择天赋")
    return get_talent_training_video(talent["talent_code"])


@router.post("/items/{item_id}/watch-progress", response_model=WatchProgressResponse)
def report_watch_progress(
    item_id: int,
    req: WatchProgressRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.record_watch_progress(
            db,
            child_user_id,
            item_id,
            watched_sec=req.watched_sec,
            duration_sec=req.duration_sec,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/entry", response_model=TrainingEntryResponse)
def training_entry(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    """训练页入口：优先检查最新天赋并同步今日方案状态"""
    return training_service.get_training_entry(db, child_user_id)


@router.get("/today", response_model=TrainingTodayResponse)
async def training_today(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
    skip_ai: bool = Query(False, description="跳过 AI 生成，加快首屏"),
):
    """今日训练方案：按天赋推送音频 + AI 生成今日指令（参考昨日打卡）"""
    try:
        return await ensure_plan_report(db, child_user_id, plan_date, skip_ai=skip_ai)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/checkin", response_model=CheckinResponse)
def training_checkin(
    req: CheckinRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.submit_checkin(
            db,
            child_user_id,
            plan_id=req.plan_id,
            item_id=req.item_id,
            ability_type=req.ability_type,
            time_spent=req.time_spent,
            content=req.content,
            result=req.result,
            note=req.note,
            attitude_pct=req.attitude_pct,
            cards=req.cards,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/checkin/today", response_model=list[CheckinRecordOut])
def checkin_today(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    return training_service.get_today_checkins(db, child_user_id, plan_date)


@router.get("/checkin/{record_id}", response_model=CheckinRecordOut)
def get_checkin(
    record_id: int,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.get_checkin_record(db, child_user_id, record_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.put("/checkin/{record_id}")
def update_checkin(
    record_id: int,
    req: CheckinUpdateRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.update_checkin_record(
            db,
            child_user_id,
            record_id,
            ability_type=req.ability_type,
            time_spent=req.time_spent,
            content=req.content,
            result=req.result,
            note=req.note,
            attitude_pct=req.attitude_pct,
            cards=req.cards,
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.delete("/checkin/{record_id}", response_model=CheckinDeleteResponse)
def delete_checkin(
    record_id: int,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.delete_checkin_record(db, child_user_id, record_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/progress", response_model=TrainingProgressResponse)
def training_progress(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return training_service.get_progress(db, child_user_id)


@router.post("/window", response_model=WindowResponse)
def set_window(
    req: WindowSetRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return training_service.set_training_window(
            db, child_user_id, req.start_time, req.end_time
        )
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/window", response_model=WindowResponse)
def get_window(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    row = training_service.get_training_window(db, child_user_id)
    if not row:
        raise HTTPException(404, "今日尚未设置训练时段")
    return row


@router.delete("/window")
def delete_window(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    deleted = training_service.clear_training_window(db, child_user_id)
    return {"deleted": deleted}


@router.get("/window/status", response_model=WindowStatusResponse)
def window_status(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return training_service.get_window_status(db, child_user_id)


@router.post("/plan/media-exhausted", response_model=TrainingTodayResponse)
def mark_plan_media_exhausted(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    """设定时长用尽：隐藏音视频，打卡仍开放至训练日截止"""
    try:
        return training_service.mark_today_media_exhausted(db, child_user_id, plan_date)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/report/today", response_model=TrainingTodayResponse)
async def training_report_today(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    force: bool = Query(False, description="强制重新生成 AI 方案"),
    skip_ai: bool = Query(False),
):
    try:
        return await ensure_plan_report(db, child_user_id, force=force, skip_ai=skip_ai)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.get("/report/{plan_date}", response_model=TrainingTodayResponse)
def training_report_by_date(
    plan_date: date,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    data = training_service.get_plan_by_date(db, child_user_id, plan_date)
    if not data:
        raise HTTPException(404, "该日期无训练方案")
    return data


@router.get("/history", response_model=CheckinHistoryResponse)
def training_history(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(60, ge=1, le=200),
    group_by_day: bool = Query(True),
    exclude_today: bool = Query(False),
):
    items = training_service.get_checkin_history(
        db, child_user_id, limit, exclude_today=exclude_today
    )
    days = training_service.group_checkin_history_by_day(items) if group_by_day else []
    return {"items": items, "days": days}
