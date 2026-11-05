"""用户端 JWT access_token（HS256）— Admin 仍走 Cookie opaque session"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt

logger = logging.getLogger("jnao")

ALGORITHM = "HS256"
DEFAULT_TTL_DAYS = 7


def _secret() -> str:
    secret = (os.getenv("JWT_SECRET") or os.getenv("JNAO_JWT_SECRET") or "").strip()
    if secret:
        return secret
    # 开发回退；生产应配置 JWT_SECRET
    fallback = (os.getenv("JNAO_SECRET_KEY") or "jnao-dev-jwt-secret-change-me-32b!!").strip()
    if not getattr(_secret, "_warned", False):
        logger.warning("JWT_SECRET 未配置，使用开发回退密钥")
        _secret._warned = True  # type: ignore[attr-defined]
    return fallback


def ttl_days() -> int:
    raw = (os.getenv("JWT_TTL_DAYS") or "").strip()
    if raw:
        try:
            return max(1, min(30, int(raw)))
        except ValueError:
            pass
    return DEFAULT_TTL_DAYS


def looks_like_jwt(token: str | None) -> bool:
    if not token or token.count(".") != 2:
        return False
    # opaque session 为 64 hex，不含点
    return True


def mint_access_token(
    *,
    user_id: int,
    role: str,
    sid: int,
    jti: str,
    ttl: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    days = ttl if ttl is not None else ttl_days()
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": int(sid),
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=days),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """校验并返回 payload；失败抛 jwt 异常。"""
    return jwt.decode(
        token,
        _secret(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "sid", "jti", "exp"]},
    )
