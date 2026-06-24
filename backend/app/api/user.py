"""用户资料 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_child_user_id, get_db
from app.services import user_service

router = APIRouter(prefix="/api/user", tags=["user"])


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, max_length=50)
    jnao_uid: str | None = None
    profile_json: dict | None = None
    training_level: str | None = None


@router.get("/profile")
def get_profile(
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    user = user_service.get_profile(db, child_user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return user_service.profile_to_dict(user)


@router.put("/profile")
def update_profile(
    req: ProfileUpdateRequest,
    child_user_id: int = Depends(get_child_user_id),
    db: Session = Depends(get_db),
):
    user = user_service.update_profile(
        db,
        child_user_id,
        nickname=req.nickname,
        jnao_uid=req.jnao_uid,
        profile_json=req.profile_json,
        training_level=req.training_level,
    )
    if not user:
        raise HTTPException(404, "用户不存在")
    return user_service.profile_to_dict(user)
