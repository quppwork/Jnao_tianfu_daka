"""FastAPI 依赖注入"""

from fastapi import Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db as _get_db


def get_db():
    yield from _get_db()


def get_child_user_id(
    user_id: int | None = Query(None, description="孩子用户 ID"),
    x_child_user_id: int | None = Header(None, alias="X-Child-User-Id"),
) -> int:
    uid = user_id or x_child_user_id
    if not uid:
        raise HTTPException(401, "需要 user_id 参数或 X-Child-User-Id 请求头")
    return uid
