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

from app.api import auth, chat, dev, growth, guide, health, parent, qa, resources, talent, training, user, voice
from app.core.logger import setup_logging
from app.core.security import get_cors_origins, is_debug_routes_enabled
from app.db.models import ContentItem
from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_all_xet_catalogs

logger = setup_logging("jnao")


def _seed_catalog_if_empty() -> None:
    session = get_session_factory()()
    try:
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
    logger.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"<-- {request.method} {request.url.path} {response.status_code}")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Child-User-Id"],
)

app.include_router(health.router)
app.include_router(talent.router)
app.include_router(chat.router)
app.include_router(guide.router)
app.include_router(voice.router)
app.include_router(auth.router)
app.include_router(parent.router)
app.include_router(user.router)
app.include_router(training.router)
app.include_router(dev.router)
app.include_router(resources.router)
app.include_router(qa.router)
app.include_router(growth.router)
