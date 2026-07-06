"""FastAPI 依赖注入"""

import logging

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db

logger = logging.getLogger("jnao")


def get_db():
    yield from _get_db()


def get_child_user_id(
    user_id: int | None = Query(None, ge=1, description="孩子用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
) -> int:
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的 user_id 参数或 X-Child-User-Id 请求头")
    return uid


def get_authenticated_user(
    user_id: int | None = Query(None, ge=1, description="孩子用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    session_token: str | None = Query(None, description="会话令牌"),
    db: Session = Depends(get_db),
) -> int:
    """验证 user_id + session_token。"""
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的 user_id 参数或 X-Child-User-Id 请求头")

    from app.db.models import ChildUser

    try:
        user = db.get(ChildUser, uid)
    except Exception as e:
        logger.error("get_authenticated_user: 读取用户失败 uid=%s: %s", uid, e)
        raise HTTPException(503, "认证服务暂不可用，请稍后重试") from e

    if not user:
        raise HTTPException(401, "用户不存在")

    from app.services.auth_service import is_account_active
    from app.services.session_service import validate_session

    if not is_account_active(user):
        raise HTTPException(401, "账号已停用")

    token = x_session_token or session_token
    if not token:
        raise HTTPException(401, "需要有效的 session_token（请重新登录）")

    if not validate_session(db, uid, token):
        raise HTTPException(401, "已在其他设备登录或会话已失效，请重新登录")

    return uid


def get_authenticated_student(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> int:
    """学生端 API：在 session 有效基础上要求 role=student。"""
    from app.db.models import ChildUser
    from app.services import auth_service

    user = db.get(ChildUser, user_id)
    if not user or (user.role or auth_service.ROLE_STUDENT) != auth_service.ROLE_STUDENT:
        raise HTTPException(403, "需要学生账号")
    return user_id


def get_admin_user(
    user_id: int | None = Query(None, ge=1, description="管理员用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    session_token: str | None = Query(None, description="会话令牌"),
    db: Session = Depends(get_db),
) -> int:
    """验证管理员 session_token + role=admin"""
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的管理员 user_id")

    from app.db.models import ChildUser
    from app.services import auth_service

    user = db.get(ChildUser, uid)
    if not user or user.role != auth_service.ROLE_ADMIN:
        raise HTTPException(403, "需要管理员权限")

    from app.services.auth_service import is_account_active
    from app.services.session_service import validate_session

    if not is_account_active(user):
        raise HTTPException(401, "管理员账号已停用")

    token = x_session_token or session_token
    if not token:
        raise HTTPException(401, "管理员会话无效，请重新登录")
    if not validate_session(db, uid, token):
        raise HTTPException(401, "管理员会话无效或已在其他设备登录，请重新登录")
    return uid
