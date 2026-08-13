"""成就/荣誉系统 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cache import (
    cache_get_json,
    cache_set_json,
    invalidate_user_achievement,
    key_achievement_list,
    ttl_env,
)
from app.core.deps import get_authenticated_student, get_db
from app.services import achievement_service
from app.services.achievement_service import AchievementError

router = APIRouter(prefix="/api/achievement", tags=["achievement"])


# ─── 请求/响应模型 ────────────────────────────────────────


class ClaimRequest(BaseModel):
    achievement_id: int


class SetTitleRequest(BaseModel):
    title_code: str


class SetShowcaseRequest(BaseModel):
    slot_index: int
    achievement_id: int | None = None


# ─── 勋章列表与详情 ────────────────────────────────────────


@router.get("/list")
def get_achievement_list(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """获取用户勋章列表（含进度和状态）"""
    cache_key = key_achievement_list(child_user_id)
    cached = cache_get_json(cache_key)
    if isinstance(cached, dict) and cached.get("items") is not None:
        return cached

    achievement_service.check_and_update_achievements(db, child_user_id)
    items = achievement_service.get_user_achievements(db, child_user_id)
    stats = achievement_service.stats_from_items(items)
    payload = {"items": items, "stats": stats}
    cache_set_json(cache_key, payload, ttl_env("CACHE_TTL_ACHIEVEMENT", 60))
    return payload


@router.get("/stats")
def get_achievement_stats(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """获取成就统计"""
    return achievement_service.get_achievement_stats(db, child_user_id)


# ─── 勋章解锁 ────────────────────────────────────────


@router.post("/claim")
def claim_achievement(
    req: ClaimRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """领取勋章（ready → claimed）"""
    try:
        result = achievement_service.claim_achievement(db, child_user_id, req.achievement_id)
        return {"success": True, "data": result}
    except AchievementError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/check")
def check_achievements(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """手动触发检查（返回新解锁的勋章）"""
    newly_ready = achievement_service.check_and_update_achievements(db, child_user_id)
    invalidate_user_achievement(child_user_id)
    return {"newly_ready": newly_ready, "count": len(newly_ready)}


# ─── 称号管理 ────────────────────────────────────────


@router.get("/title")
def get_user_title(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """获取当前称号"""
    title = achievement_service.get_user_title(db, child_user_id)
    return {"title": title}


@router.post("/title")
def set_user_title(
    req: SetTitleRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """设置当前称号（必须已解锁）"""
    try:
        result = achievement_service.set_user_title(db, child_user_id, req.title_code)
        return {"success": True, "data": result}
    except AchievementError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── 荣誉展柜 ────────────────────────────────────────


@router.get("/showcase")
def get_showcase(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """获取荣誉展柜"""
    slots = achievement_service.get_showcase(db, child_user_id)
    return {"slots": slots}


@router.post("/showcase")
def set_showcase_slot(
    req: SetShowcaseRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """设置展柜槽位"""
    try:
        result = achievement_service.set_showcase_slot(
            db, child_user_id, req.slot_index, req.achievement_id
        )
        return {"success": True, "data": result}
    except AchievementError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ─── 管理接口（初始化）────────────────────────────────────────


@router.post("/admin/init")
def init_achievements(
    db: Session = Depends(get_db),
):
    """初始化勋章定义（管理员）"""
    # TODO: 添加管理员鉴权
    count = achievement_service.init_achievement_definitions(db)
    return {"inserted": count, "message": f"成功初始化 {count} 个勋章定义"}
