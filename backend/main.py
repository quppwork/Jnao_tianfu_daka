"""JNAO Backend — 集中平台 API

启动: uvicorn main:app --host 127.0.0.1 --port 8012 --reload
"""

from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import admin, auth, dev, growth, guide, health, meta, parent, qa, resources, talent, training, user, voice
from app.core.logger import setup_logging
from app.core.security import get_cors_origins, is_debug_routes_enabled
from app.db.models import ContentItem
from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_all_xet_catalogs

logger = setup_logging("jnao")


def _seed_catalog_if_empty() -> None:
    session = get_session_factory()()
    try:
        from app.services.auth_service import ensure_admin_account

        if os.getenv("JNAO_SKIP_ADMIN_SEED") != "1":
            ensure_admin_account(session)
        count = session.scalar(select(func.count()).select_from(ContentItem)) or 0
        if count == 0:
            inserted = sum(import_all_xet_catalogs(session).values())
            logger.info(f"音频目录自动导入 {inserted} 条")
        else:
            from app.services.training_catalog_sync import ensure_supplementary_catalogs

            added = ensure_supplementary_catalogs(session)
            if added:
                logger.info(f"补充音频目录导入 {added} 条（多元感知等）")
    except Exception as e:
        logger.warning(f"音频目录导入跳过: {e}")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.runtime import init_runtime, should_force_relogin_on_boot, warn_redis_once
    from app.core.security import assert_production_auth_config

    assert_production_auth_config()
    boot_id = init_runtime()
    warn_redis_once(logger)
    logger.info(
        "runtime ready boot_id=%s force_relogin_on_boot=%s",
        boot_id[:8],
        should_force_relogin_on_boot(),
    )
    init_db()
    _seed_catalog_if_empty()
    yield


_debug = is_debug_routes_enabled()
app = FastAPI(
    title="JNAO API",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)


@app.get("/")
def root():
    """根路径说明 — 8012 为 API，产品页面在前端"""
    return {
        "name": "JNAO 天赋成长平台 API",
        "version": "0.3.0",
        "message": "这是后端 API 服务。请在浏览器打开前端地址使用训练、测评等功能。",
        "frontend": "http://127.0.0.1:5185",
        "docs": "/docs",
        "health": "/api/health",
        "ping": "/api/ping",
    }


@app.middleware("http")
async def log_requests(request, call_next):
    import time

    from app.core.biz_log import (
        bind_user,
        biz_event,
        get_request_id,
        get_user_id,
        new_request_id,
        reset_context,
        set_request_id,
        should_log_http,
    )

    reset_context()
    rid = request.headers.get("X-Request-Id") or new_request_id()
    set_request_id(rid)

    # 尽早带上客户端声明的 uid（鉴权后再由 deps 覆盖为已验证 uid）
    hint = request.headers.get("X-Child-User-Id") or request.query_params.get("user_id")
    try:
        if hint and str(hint).isdigit() and int(hint) > 0:
            bind_user(int(hint))
    except Exception:
        pass

    path = request.url.path
    quiet = path == "/api/ping" or path == "/api/health"
    t0 = time.perf_counter()
    if not quiet:
        logger.info(
            "--> %s %s uid=%s rid=%s",
            request.method,
            path,
            hint or "-",
            get_request_id(),
        )
    try:
        response = await call_next(request)
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        biz_event(
            "http.error",
            result="error",
            ms=ms,
            level="error",
            method=request.method,
            path=path,
            err=type(e).__name__,
        )
        raise
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-Id"] = get_request_id()
    status = response.status_code
    uid_now = get_user_id() or hint or "-"
    if not quiet:
        logger.info(
            "<-- %s %s %s uid=%s rid=%s ms=%.0f",
            request.method,
            path,
            status,
            uid_now,
            get_request_id(),
            ms,
        )
    elif status >= 400:
        logger.warning(f"<-- {request.method} {path} {status}")

    if should_log_http(path, status):
        biz_event(
            "http.request",
            result="ok" if status < 400 else f"http_{status}",
            ms=ms,
            level="info" if status < 400 else "warning",
            method=request.method,
            path=path,
            status=status,
        )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Child-User-Id", "X-Session-Token", "X-Device-Id", "X-Request-Id"],
    expose_headers=["X-Request-Id"],
)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(talent.router)
app.include_router(guide.router)
app.include_router(voice.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(parent.router)
app.include_router(user.router)
app.include_router(training.router)
app.include_router(dev.router)
app.include_router(resources.router)
app.include_router(qa.router)
app.include_router(growth.router)
