"""FastAPI 依赖注入"""

import logging

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db

logger = logging.getLogger("jnao")


def _is_missing_column_error(exc: Exception) -> bool:
    """迁移未完成时 session_token 等列可能不存在，仅此场景允许降级。"""
    msg = str(exc).lower()
    return "no such column" in msg or "unknown column" in msg


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
    """验证 user_id + session_token，新登录会使旧设备 token 失效。

    单设备登录：每次登录刷新 session_token，旧 token 立即失效。
    向下兼容：用户无 token 时自动补发（首次迁移场景）。
    防御处理：session_token 列不存在时自动降级为无 token 验证。
    """
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的 user_id 参数或 X-Child-User-Id 请求头")

    from app.db.models import ChildUser

    try:
        user = db.get(ChildUser, uid)
    except Exception as e:
        if _is_missing_column_error(e):
            logger.warning("get_authenticated_user: session_token 列未创建，降级为无 token 验证")
            return uid
        raise

    if not user:
        raise HTTPException(401, "用户不存在")

    from app.services.auth_service import is_account_active
    from app.services.session_service import validate_session

    if not is_account_active(user):
        raise HTTPException(401, "账号已停用")

    token = x_session_token or session_token

    try:
        user.session_token  # 触发 ORM 加载，列缺失时在此抛出
    except Exception as e:
        if _is_missing_column_error(e):
            logger.warning("get_authenticated_user: 读取 session_token 列失败，降级处理")
            return uid
        raise

    if not token:
        raise HTTPException(401, "需要有效的 session_token（请重新登录）")

    if not validate_session(db, uid, token):
        raise HTTPException(401, "已在其他设备登录或会话已失效，请重新登录")

    return uid


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
