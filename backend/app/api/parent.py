"""家长端 API — 孩子账号分配与管理"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.core.cache import invalidate_user_profile
from app.core.session_cookie import set_session_cookie
from app.schemas.auth import (
    ChildDetailResponse,
    ChildSummaryOut,
    CreateChildRequest,
    ParentChildrenResponse,
    ParentProfileResponse,
    ParentProfileUpdateRequest,
    ParentQuotaResponse,
    UpdateChildRequest,
)
from app.services import parent_service
from app.services.parent_profile_service import parent_profile_to_dict, update_parent_profile, assert_parent_account_ready

router = APIRouter(prefix="/api/parent", tags=["parent"])


def _require_parent_id(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> int:
    from app.services import auth_service

    user = auth_service.get_child_user(db, user_id)
    if not user or user.role != auth_service.ROLE_PARENT:
        raise HTTPException(403, "需要家长账号")
    return user_id


@router.get("/profile", response_model=ParentProfileResponse)
def get_profile(
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from app.services import auth_service

    user = auth_service.get_child_user(db, user_id)
    return ParentProfileResponse(**parent_profile_to_dict(user))


@router.put("/profile", response_model=ParentProfileResponse)
def put_profile(
    req: ParentProfileUpdateRequest,
    response: Response,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    user, new_token = update_parent_profile(
        db,
        user_id,
        nickname=req.nickname,
        real_name=req.real_name,
        password=req.password,
        old_password=req.old_password,
        require_password=req.require_password,
    )
    if new_token:
        from app.services import auth_service

        set_session_cookie(response, new_token, role=auth_service.ROLE_PARENT)
    invalidate_user_profile(user_id)
    return ParentProfileResponse(**parent_profile_to_dict(user, session_token=new_token))


@router.get("/quota", response_model=ParentQuotaResponse)
def get_quota(user_id: int = Depends(_require_parent_id), db: Session = Depends(get_db)):
    """预留：查询家长可分配的孩子名额"""
    return parent_service.get_quota(db, user_id)


@router.get("/children", response_model=ParentChildrenResponse)
def list_children(user_id: int = Depends(_require_parent_id), db: Session = Depends(get_db)):
    items = parent_service.list_children(db, user_id)
    return ParentChildrenResponse(children=[ChildSummaryOut(**c) for c in items])


@router.post("/children", response_model=ChildSummaryOut)
def create_child(
    req: CreateChildRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    from app.services import auth_service

    parent = auth_service.get_child_user(db, user_id)
    assert_parent_account_ready(parent)
    child = parent_service.create_child(
        db,
        user_id,
        login_name=req.login_name,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
        region=req.region,
    )
    from app.services import auth_service

    invalidate_user_profile(child.id)
    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.put("/children/{child_id}", response_model=ChildSummaryOut)
def update_child(
    child_id: int,
    req: UpdateChildRequest,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    child = parent_service.update_child(
        db,
        user_id,
        child_id,
        nickname=req.nickname,
        password=req.password,
        grade=req.grade,
        age=req.age,
        region=req.region,
    )
    from app.services import auth_service

    invalidate_user_profile(child.id)
    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.delete("/children/{child_id}")
def delete_child(
    child_id: int,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    parent_service.delete_child(db, user_id, child_id)
    return {"ok": True}


@router.get("/children/{child_id}/summary", response_model=ChildDetailResponse)
def child_summary(
    child_id: int,
    user_id: int = Depends(_require_parent_id),
    db: Session = Depends(get_db),
):
    """预留：家长查看单个孩子信息摘要"""
    data = parent_service.get_child_detail(db, user_id, child_id)
    return ChildDetailResponse(**data)
