"""成长里程碑 API"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_db
from app.core.cache import (
    cache_get_json,
    cache_set_json,
    key_growth,
    ttl_env,
)
from app.services import growth_service

router = APIRouter(prefix="/api/growth", tags=["growth"])

_GROWTH_TTL = ttl_env("CACHE_TTL_GROWTH_SUMMARY", 120)


def _cached_growth(user_id: int, bucket: str, loader):
    key = key_growth(bucket, user_id)
    cached = cache_get_json(key)
    if cached is not None:
        return cached
    data = loader()
    cache_set_json(key, data, _GROWTH_TTL)
    return data


@router.get("/badges")
def get_badges(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    items = _cached_growth(
        child_user_id,
        "badges",
        lambda: growth_service.get_badges(db, child_user_id),
    )
    return {"items": items}


@router.get("/milestones")
def get_milestones(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    items = _cached_growth(
        child_user_id,
        "milestones",
        lambda: growth_service.get_milestones(db, child_user_id),
    )
    return {"items": items}


@router.get("/timeline")
def get_timeline(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    limit: int = Query(40, ge=1, le=100),
):
    items = _cached_growth(
        child_user_id,
        f"timeline:{limit}",
        lambda: growth_service.get_timeline(db, child_user_id, limit=limit),
    )
    return {"items": items}


@router.get("/summary")
def get_summary(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return _cached_growth(
        child_user_id,
        "summary",
        lambda: growth_service.get_summary(db, child_user_id),
    )


@router.get("/share")
def get_share(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return _cached_growth(
        child_user_id,
        "share",
        lambda: growth_service.get_share(db, child_user_id),
    )
