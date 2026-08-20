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
from app.services import growth_service, academic_plan_service

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


@router.get("/calendar")
def get_calendar(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    items = _cached_growth(
        child_user_id,
        "calendar",
        lambda: growth_service.get_calendar_days(db, child_user_id),
    )
    return {"items": items}


@router.get("/tier")
def get_tier(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    return _cached_growth(
        child_user_id,
        "tier",
        lambda: growth_service.get_tier_brief(db, child_user_id),
    )


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


@router.get("/academic-plan")
async def get_academic_plan(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
    refresh: bool = Query(False, description="强制刷新AI生成"),
):
    """获取学业规划报告（基于训练数据 + AI生成）"""
    # 学业规划缓存1小时，避免频繁调用AI
    cache_key = "academic-plan"
    if not refresh:
        cached = cache_get_json(key_growth(cache_key, child_user_id))
        if cached is not None:
            return cached
    
    plan = await academic_plan_service.generate_academic_plan(db, child_user_id)
    cache_set_json(key_growth(cache_key, child_user_id), plan, ttl_env("CACHE_TTL_ACADEMIC_PLAN", 3600))
    return plan
