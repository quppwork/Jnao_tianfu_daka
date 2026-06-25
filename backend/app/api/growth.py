"""成长里程碑 API"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.services import growth_service

router = APIRouter(prefix="/api/growth", tags=["growth"])


@router.get("/badges")
def get_badges(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return {"items": growth_service.get_badges(db, child_user_id)}


@router.get("/milestones")
def get_milestones(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return {"items": growth_service.get_milestones(db, child_user_id)}


@router.get("/timeline")
def get_timeline(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
    limit: int = Query(40, ge=1, le=100),
):
    return {"items": growth_service.get_timeline(db, child_user_id, limit=limit)}


@router.get("/summary")
def get_summary(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return growth_service.get_summary(db, child_user_id)


@router.get("/share")
def get_share(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    return growth_service.get_share(db, child_user_id)
