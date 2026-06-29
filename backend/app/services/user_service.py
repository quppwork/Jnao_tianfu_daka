"""用户资料"""

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from app.services.assessment_service import enrich_profile_talent_fields
from app.services.onboarding_service import (
    merge_onboarding_into_profile,
    validate_onboarding_merge,
)


def merge_profile_json(current: dict | None, patch: dict) -> dict:
    """深度合并 profile_json — onboarding 支持分步保存与老学员 prior_training_data"""
    if patch.get("onboarding"):
        current_ob = (current or {}).get("onboarding") if isinstance((current or {}).get("onboarding"), dict) else {}
        validate_onboarding_merge(current_ob, patch["onboarding"])
        return merge_onboarding_into_profile(current, patch)
    base = dict(current or {})
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **val}
        else:
            base[key] = val
    return base


def get_profile(db: Session, child_user_id: int) -> ChildUser | None:
    return db.get(ChildUser, child_user_id)


def update_profile(
    db: Session,
    child_user_id: int,
    *,
    nickname: str | None = None,
    jnao_uid: str | None = None,
    profile_json: dict | None = None,
    training_level: str | None = None,
) -> ChildUser | None:
    user = db.get(ChildUser, child_user_id)
    if not user:
        return None
    if nickname is not None:
        user.nickname = nickname
    if jnao_uid is not None:
        user.jnao_uid = jnao_uid
    if profile_json is not None:
        user.profile_json = merge_profile_json(user.profile_json, profile_json)
        from app.services.assessment_service import sync_child_user_talent

        sync_child_user_talent(db, child_user_id)
    if training_level is not None:
        user.training_level = training_level
    db.commit()
    db.refresh(user)
    return user


def merge_learner_profile(db: Session, child_user_id: int, patch: dict) -> ChildUser | None:
    user = db.get(ChildUser, child_user_id)
    if not user:
        return None
    current = dict(user.profile_json or {})
    current.update(patch)
    user.profile_json = current
    db.commit()
    db.refresh(user)
    return user


def profile_to_dict(user: ChildUser, db: Session | None = None) -> dict:
    data = {
        "child_user_id": user.id,
        "parent_phone": user.parent_phone,
        "nickname": user.nickname,
        "jnao_uid": user.jnao_uid,
        "profile_json": user.profile_json or {},
        "training_level": user.training_level,
        "is_qingbei": bool(user.is_qingbei),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    if db is not None:
        enrich_profile_talent_fields(db, user.id, data)
    return data
