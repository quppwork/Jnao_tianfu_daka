"""HttpOnly Session Cookie — 替代前端 localStorage 明文 token"""

from __future__ import annotations

import os

from fastapi import Request, Response

from app.core.security import is_production
from app.services import auth_service

COOKIE_USER = "jnao_session"
COOKIE_ADMIN = "jnao_admin_session"
SESSION_MAX_AGE = 7 * 24 * 3600


def cookies_enabled() -> bool:
    return os.getenv("SESSION_USE_HTTPONLY_COOKIE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def expose_token_in_json() -> bool:
    return os.getenv("SESSION_EXPOSE_TOKEN_IN_JSON", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _cookie_secure() -> bool:
    if is_production():
        return True
    return os.getenv("SESSION_COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes")


def _cookie_samesite() -> str:
    raw = (os.getenv("SESSION_COOKIE_SAMESITE", "lax") or "lax").strip().lower()
    return raw if raw in ("lax", "strict", "none") else "lax"


def cookie_name_for_role(role: str | None) -> str:
    if (role or "").strip() == auth_service.ROLE_ADMIN:
        return COOKIE_ADMIN
    return COOKIE_USER


def read_session_cookie(request: Request, *, path: str | None = None) -> str | None:
    if not cookies_enabled():
        return None
    p = path or request.url.path
    name = COOKIE_ADMIN if p.startswith("/api/admin/") else COOKIE_USER
    token = request.cookies.get(name)
    return token.strip() if token and token.strip() else None


def set_session_cookie(response: Response, token: str, *, role: str) -> None:
    if not cookies_enabled() or not token:
        return
    name = cookie_name_for_role(role)
    response.set_cookie(
        key=name,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        path="/api",
        max_age=SESSION_MAX_AGE,
    )
    other = COOKIE_USER if name == COOKIE_ADMIN else COOKIE_ADMIN
    response.delete_cookie(key=other, path="/api")


def clear_session_cookie(response: Response, *, role: str | None = None) -> None:
    if role == auth_service.ROLE_ADMIN:
        response.delete_cookie(key=COOKIE_ADMIN, path="/api")
        return
    if role in (auth_service.ROLE_PARENT, auth_service.ROLE_STUDENT, None):
        response.delete_cookie(key=COOKIE_USER, path="/api")
    if role is None:
        response.delete_cookie(key=COOKIE_ADMIN, path="/api")


def maybe_strip_token(token: str | None) -> str | None:
    if expose_token_in_json():
        return token
    return None
