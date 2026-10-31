"""用户资料 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_student, get_db
from app.core.cache import (
    cache_get_json,
    cache_set_json,
    invalidate_user_assessment,
    invalidate_user_growth,
    invalidate_user_profile,
    invalidate_user_training,
    key_profile,
    ttl_env,
)
from app.services import assessment_service, user_service
from app.services.onboarding_service import OnboardingError

router = APIRouter(prefix="/api/user", tags=["user"])

_PROFILE_TTL = ttl_env("CACHE_TTL_PROFILE", 300)


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, max_length=50)
    jnao_uid: str | None = None
    profile_json: dict | None = None
    training_level: str | None = None


class LearnerProfileUpdate(BaseModel):
    age: int | None = Field(None, ge=5, le=25)
    grade: str | None = Field(None, max_length=20)
    school_stage: str | None = Field(
        None,
        pattern="^(primary_low|primary_high|junior|senior)$",
    )
    subject_pref: str | None = Field(None, max_length=20)


@router.get("/profile")
def get_profile(
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    repaired = assessment_service.ensure_onboarding_completed_after_assessment(db, child_user_id)
    key = key_profile(child_user_id)
    cached = None if repaired else cache_get_json(key)
    if cached is not None:
        pj = cached.get("profile_json")
        if isinstance(pj, dict):
            cached["profile_json"] = user_service.normalize_profile_json(pj)
        return cached
    user = user_service.get_profile(db, child_user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    data = user_service.profile_to_dict(user, db)
    cache_set_json(key, data, _PROFILE_TTL)
    return data


@router.put("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    try:
        user = user_service.update_profile(
            db,
            child_user_id,
            nickname=req.nickname,
            jnao_uid=req.jnao_uid,
            profile_json=req.profile_json,
            training_level=req.training_level,
        )
    except OnboardingError as e:
        raise HTTPException(e.status_code, e.message) from e
    if not user:
        raise HTTPException(404, "用户不存在")
    # 若 profile_json 包含 onboarding 自选天赋，同步提升到 child_user 顶层字段
    from app.services.assessment_service import repair_onboarding_talent, sync_child_user_talent
    repair_onboarding_talent(db, child_user_id)
    sync_child_user_talent(db, child_user_id)
    invalidate_user_profile(child_user_id)
    return user_service.profile_to_dict(user, db)


@router.put("/learner-profile")
def update_learner_profile(
    req: LearnerProfileUpdate,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    patch = req.model_dump(exclude_none=True)
    user = user_service.merge_learner_profile(db, child_user_id, patch)
    if not user:
        raise HTTPException(404, "用户不存在")
    invalidate_user_profile(child_user_id)
    return user_service.profile_to_dict(user, db)


class TalentConflictResolve(BaseModel):
    action: str = Field(..., pattern="^(keep_old|use_new)$")


@router.post("/talent/resolve-conflict")
def resolve_talent_conflict(
    req: TalentConflictResolve,
    child_user_id: int = Depends(get_authenticated_student),
    db: Session = Depends(get_db),
):
    """解决天赋冲突：保留旧天赋或采用新测评结果"""
    try:
        result = assessment_service.resolve_talent_conflict(
            db, child_user_id, action=req.action
        )
        invalidate_user_assessment(child_user_id)
        invalidate_user_profile(child_user_id)
        invalidate_user_growth(child_user_id)
        invalidate_user_training(child_user_id)
        return result
    except assessment_service.AssessmentError as e:
        raise HTTPException(e.status_code, e.message) from e
