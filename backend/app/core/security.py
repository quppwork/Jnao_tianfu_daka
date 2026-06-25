"""环境与访问控制 — 本地开发默认宽松，生产通过 JNAO_ENV=production 收紧"""

import os


def get_env() -> str:
    return os.getenv("JNAO_ENV", "development").strip().lower()


def is_production() -> bool:
    return get_env() == "production"


def is_dev_api_enabled() -> bool:
    """开发者 API（/api/dev/*）是否可用"""
    default = "0" if is_production() else "1"
    return os.getenv("JNAO_DEV_MODE", default) == "1"


def is_debug_routes_enabled() -> bool:
    """调试路由（/api/guide/debug 等）与 OpenAPI 文档"""
    if is_production():
        return os.getenv("JNAO_DEBUG_ROUTES", "0") == "1"
    return os.getenv("JNAO_DEBUG_ROUTES", "1") == "1"


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://127.0.0.1:5185",
        "http://localhost:5185",
        "http://127.0.0.1:5186",
        "http://localhost:5186",
        "http://127.0.0.1:5187",
        "http://localhost:5187",
    ]
