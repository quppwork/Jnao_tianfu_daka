"""用户资料"""

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from app.services.assessment_service import get_latest_assessment


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
        user.profile_json = profile_json
    if training_level is not None:
        user.training_level = training_level
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
        latest = get_latest_assessment(db, user.id)
        if latest:
            data["talent_code"] = latest.talent_code
            data["talent_tag"] = latest.talent_tag
            data["talent_primary"] = latest.talent_primary
            data["latest_assessment_id"] = latest.id
    return data
