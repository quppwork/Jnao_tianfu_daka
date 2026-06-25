"""开发者 API — 仅 JNAO_DEV_MODE=1 时可用"""

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.services.dev_training_service import (
    get_dev_training_status,
    reset_all_training,
    reset_today_training,
    simulate_next_training_day,
)
from app.services.training_service import TrainingError

router = APIRouter(prefix="/api/dev", tags=["dev"])


def _require_dev_mode() -> None:
    if os.getenv("JNAO_DEV_MODE", "1") != "1":
        raise HTTPException(403, "开发者 API 已关闭（设置 JNAO_DEV_MODE=1 启用）")


@router.get("/training/status")
def dev_training_status(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return get_dev_training_status(db, child_user_id)


@router.post("/training/reset-today")
def dev_reset_today(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return reset_today_training(db, child_user_id)


@router.post("/training/reset-all")
def dev_reset_all(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return reset_all_training(db, child_user_id)


@router.post("/training/next-day")
def dev_next_day(
    _: None = Depends(_require_dev_mode),
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    try:
        return simulate_next_training_day(db, child_user_id)
    except TrainingError as e:
        raise HTTPException(e.status_code, e.message) from e
