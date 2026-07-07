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


def is_legacy_register_enabled() -> bool:
    """MVP 遗留 /api/auth/register — 生产默认关闭。"""
    default = "0" if is_production() else "1"
    return os.getenv("JNAO_LEGACY_REGISTER", default) == "1"


def assert_production_auth_config() -> None:
    """生产环境禁止 mock 认证组件，并要求 Redis。"""
    if not is_production():
        return
    if os.getenv("AUTH_CHALLENGE_MOCK", "0") == "1":
        raise RuntimeError("生产环境不可启用 AUTH_CHALLENGE_MOCK")
    if os.getenv("SMS_PROVIDER", "").strip().lower() == "mock":
        raise RuntimeError("生产环境不可使用 SMS_PROVIDER=mock")
    if os.getenv("SMS_MOCK_EXPOSE", "0") == "1":
        raise RuntimeError("生产环境不可启用 SMS_MOCK_EXPOSE")
    if not (os.getenv("REDIS_URL") or "").strip():
        raise RuntimeError("生产环境必须配置 REDIS_URL（OAuth/SMS 状态存储）")


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
