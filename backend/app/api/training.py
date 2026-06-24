"""今日训练 API — 方案、打卡、时段"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.schemas.training import (
    CheckinRequest,
    CheckinResponse,
    TrainingProgressResponse,
    TrainingTodayResponse,
    WindowResponse,
    WindowSetRequest,
    WindowStatusResponse,
)
from app.services import training_service
from app.services.training_plan_generator import ensure_plan_report
from app.services.training_service import TrainingError

router = APIRouter(prefix="/api/training", tags=["training"])


@router.get("/today", response_model=TrainingTodayResponse)
def training_today(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    plan_date: date | None = Query(None),
):
    try:
        return training_service.get_or_create_today_plan(db, child_user_id, plan_date)
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


@router.get("/window/status", response_model=WindowStatusResponse)
def window_status(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return training_service.get_window_status(db, child_user_id)


@router.get("/report/today", response_model=TrainingTodayResponse)
async def training_report_today(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return await ensure_plan_report(db, child_user_id)
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


@router.get("/history")
def training_history(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    limit: int = 30,
):
    return {"items": training_service.get_checkin_history(db, child_user_id, limit)}
