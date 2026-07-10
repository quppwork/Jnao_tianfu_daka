"""FastAPI 依赖注入"""

import logging
import os

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db

logger = logging.getLogger("jnao")


def get_db():
    yield from _get_db()


def _resolve_session_token(
    request: Request,
    x_session_token: str | None,
    session_token: str | None,
) -> str | None:
    """优先 Header；其次 HttpOnly Cookie；图片等少数路径允许 query（兼容旧客户端）。"""
    if x_session_token and x_session_token.strip():
        return x_session_token.strip()

    from app.core.session_cookie import cookies_enabled, read_session_cookie

    if cookies_enabled():
        cookie_token = read_session_cookie(request)
        if cookie_token:
            return cookie_token

    path = request.url.path
    allow_query = (
        path.startswith("/api/qa/images/")
        or os.getenv("ALLOW_SESSION_TOKEN_QUERY", "0") == "1"
    )
    if allow_query and session_token and session_token.strip():
        return session_token.strip()
    if session_token and session_token.strip() and not allow_query:
        logger.warning("已拒绝 query session_token: %s", path)
    return None


def get_child_user_id(
    user_id: int | None = Query(None, ge=1, description="孩子用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
) -> int:
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的 user_id 参数或 X-Child-User-Id 请求头")
    return uid


def get_authenticated_user(
    request: Request,
    user_id: int | None = Query(None, ge=1, description="孩子用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    session_token: str | None = Query(None, description="会话令牌（已弃用，请用 Header）"),
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

    token = _resolve_session_token(request, x_session_token, session_token)
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
    if not auth_service.has_active_parent_bind(db, user_id):
        raise HTTPException(403, "账号未绑定家长，请联系管理员")
    return user_id


def get_admin_user(
    request: Request,
    user_id: int | None = Query(None, ge=1, description="管理员用户 ID"),
    x_child_user_id: int | None = Header(None, ge=1, alias="X-Child-User-Id"),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    session_token: str | None = Query(None, description="会话令牌（已弃用，请用 Header）"),
    db: Session = Depends(get_db),
) -> int:
    """验证管理员 session；先校验 token 再查 role，避免枚举 admin user_id（B12）。"""
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "管理员会话无效，请重新登录")

    token = _resolve_session_token(request, x_session_token, session_token)
    if not token:
        raise HTTPException(401, "管理员会话无效，请重新登录")

    from app.db.models import ChildUser
    from app.services import auth_service
    from app.services.auth_service import is_account_active
    from app.services.session_service import validate_session

    user = db.get(ChildUser, uid)
    if not user or not is_account_active(user):
        raise HTTPException(401, "管理员会话无效，请重新登录")
    if not validate_session(db, uid, token):
        raise HTTPException(401, "管理员会话无效或已在其他设备登录，请重新登录")
    if user.role != auth_service.ROLE_ADMIN:
        raise HTTPException(401, "管理员会话无效，请重新登录")
    return uid
