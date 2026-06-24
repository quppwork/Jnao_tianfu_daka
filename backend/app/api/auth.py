"""用户注册 / 登录（MVP）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.training import RegisterRequest, RegisterResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = auth_service.find_child_by_phone(db, req.parent_phone, req.nickname)
    if existing:
        return RegisterResponse(
            child_user_id=existing.id,
            parent_phone=existing.parent_phone,
            nickname=existing.nickname,
        )
    user = auth_service.register_child(
        db,
        parent_phone=req.parent_phone,
        nickname=req.nickname,
        jnao_uid=req.jnao_uid,
    )
    return RegisterResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
    )


@router.post("/login", response_model=RegisterResponse)
def login(req: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.find_child_by_phone(db, req.parent_phone, req.nickname)
    if not user:
        raise HTTPException(404, "用户不存在，请先注册")
    return RegisterResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
    )
