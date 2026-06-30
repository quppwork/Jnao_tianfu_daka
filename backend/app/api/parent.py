"""家长端 API — 孩子账号分配与管理"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.auth import (
    ChildDetailResponse,
    ChildSummaryOut,
    CreateChildRequest,
    ParentChildrenResponse,
    ParentQuotaResponse,
    UpdateChildRequest,
)
from app.services import parent_service

router = APIRouter(prefix="/api/parent", tags=["parent"])


@router.get("/quota", response_model=ParentQuotaResponse)
def get_quota(user_id: int = Query(...), db: Session = Depends(get_db)):
    """预留：查询家长可分配的孩子名额"""
    return parent_service.get_quota(db, user_id)


@router.get("/children", response_model=ParentChildrenResponse)
def list_children(user_id: int = Query(...), db: Session = Depends(get_db)):
    items = parent_service.list_children(db, user_id)
    return ParentChildrenResponse(children=[ChildSummaryOut(**c) for c in items])


@router.post("/children", response_model=ChildSummaryOut)
def create_child(
    req: CreateChildRequest,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    child = parent_service.create_child(
        db,
        user_id,
        login_name=req.login_name,
        nickname=req.nickname,
        password=req.password,
    )
    from app.services import auth_service

    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.put("/children/{child_id}", response_model=ChildSummaryOut)
def update_child(
    child_id: int,
    req: UpdateChildRequest,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    child = parent_service.update_child(
        db,
        user_id,
        child_id,
        nickname=req.nickname,
        password=req.password,
    )
    from app.services import auth_service

    return ChildSummaryOut(**auth_service.child_summary(db, child))


@router.delete("/children/{child_id}")
def delete_child(
    child_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    parent_service.delete_child(db, user_id, child_id)
    return {"ok": True}


@router.get("/children/{child_id}/summary", response_model=ChildDetailResponse)
def child_summary(
    child_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """预留：家长查看单个孩子信息摘要"""
    data = parent_service.get_child_detail(db, user_id, child_id)
    return ChildDetailResponse(**data)
