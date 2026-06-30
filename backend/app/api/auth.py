"""用户注册 / 登录"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_response(user) -> AuthResponse:
    return AuthResponse(
        child_user_id=user.id,
        parent_phone=user.parent_phone,
        nickname=user.nickname,
        role=user.role or auth_service.ROLE_STUDENT,
        login_name=user.login_name,
    )


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    role = req.role or auth_service.ROLE_STUDENT

    if role == auth_service.ROLE_PARENT:
        if not req.password:
            raise HTTPException(400, "家长注册需要设置密码")
        existing_parent = auth_service.find_parent_by_phone(db, req.parent_phone)
        if existing_parent:
            raise HTTPException(409, "该手机号已注册家长账号")
        user = auth_service.register_child(
            db,
            parent_phone=req.parent_phone,
            nickname=req.nickname,
            password=req.password,
            role=auth_service.ROLE_PARENT,
            child_quota=auth_service.DEFAULT_CHILD_QUOTA,
        )
        return _to_response(user)

    # 学生：兼容旧流程（手机+昵称），可选密码
    existing = auth_service.find_child_by_phone(db, req.parent_phone, req.nickname)
    if existing:
        return _to_response(existing)
    user = auth_service.register_child(
        db,
        parent_phone=req.parent_phone,
        nickname=req.nickname,
        jnao_uid=req.jnao_uid,
        password=req.password,
        login_name=req.login_name,
        role=auth_service.ROLE_STUDENT,
    )
    return _to_response(user)


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # 家长：手机号 + 密码
    if req.role == auth_service.ROLE_PARENT or (
        req.parent_phone and req.password and not req.login_name and not req.nickname
    ):
        if not req.parent_phone or not req.password:
            raise HTTPException(400, "请输入手机号和密码")
        user = auth_service.login_parent_by_password(db, req.parent_phone, req.password)
        if not user:
            raise HTTPException(401, "手机号或密码错误")
        return _to_response(user)

    # 学生：账号 + 密码
    if req.login_name and req.password:
        user = auth_service.login_student_by_password(db, req.login_name, req.password)
        if not user:
            raise HTTPException(401, "账号或密码错误")
        return _to_response(user)

    # 兼容旧流程：手机号 + 昵称（无密码）
    if req.parent_phone and req.nickname:
        user = auth_service.find_child_by_phone(db, req.parent_phone, req.nickname)
        if not user:
            raise HTTPException(404, "用户不存在，请先注册")
        return _to_response(user)

    raise HTTPException(400, "请提供有效的登录信息")
