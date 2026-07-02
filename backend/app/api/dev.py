"""开发者 API — 仅 JNAO_DEV_MODE=1 时可用"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.core.security import is_dev_api_enabled
from app.services.dev_training_service import (
    get_dev_training_status,
    reset_all_training,
    reset_talent_assessment,
    reset_today_training,
    reset_training_progress,
    simulate_4am_cutoff,
    simulate_next_training_day,
)
from app.services.training_service import TrainingError

router = APIRouter(prefix="/api/dev", tags=["dev"])


def _require_dev_mode() -> None:
    if not is_dev_api_enabled():
        raise HTTPException(403, "开发者 API 已关闭（本地开发设 JNAO_DEV_MODE=1）")


@router.get("/training/status")
def dev_training_status(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return get_dev_training_status(db, child_user_id)


@router.post("/training/reset-progress")
def dev_reset_progress(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """回到主线 A（不删历史打卡）"""
    try:
        return reset_training_progress(db, child_user_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/training/reset-today")
def dev_reset_today(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return reset_today_training(db, child_user_id)


@router.post("/training/reset-all")
def dev_reset_all(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    return reset_all_training(db, child_user_id)


@router.post("/training/reset-talent")
def dev_reset_talent(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """清除天赋测评 + 今日训练（用于测试「需先测评」流程）"""
    return reset_talent_assessment(db, child_user_id)


@router.post("/training/simulate-4am-cutoff")
def dev_simulate_4am_cutoff(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return simulate_4am_cutoff(db, child_user_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e


@router.post("/training/next-day")
def dev_next_day(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    try:
        return simulate_next_training_day(db, child_user_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e
