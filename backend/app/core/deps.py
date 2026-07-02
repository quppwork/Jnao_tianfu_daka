"""FastAPI 依赖注入"""

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db


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
    """
    uid = user_id or x_child_user_id
    if not uid or uid < 1:
        raise HTTPException(401, "需要有效的 user_id 参数或 X-Child-User-Id 请求头")

    from app.db.models import ChildUser

    user = db.get(ChildUser, uid)
    if not user:
        raise HTTPException(401, "用户不存在")

    token = x_session_token or session_token

    # 用户尚无 token（迁移前遗留）→ 自动生成一个，向下兼容
    if not user.session_token:
        from app.services.auth_service import _refresh_session_token

        _refresh_session_token(db, user)
        return uid

    # 客户端未传 token → 拒绝（新设备必须走登录流程获取 token）
    if not token:
        raise HTTPException(401, "需要有效的 session_token（请重新登录）")

    # token 不匹配 → 其他设备已登录
    if user.session_token != token:
        raise HTTPException(401, "已在其他设备登录，请重新登录")

    return uid
