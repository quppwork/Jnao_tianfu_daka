"""JNAO Backend — 集中平台 API

启动: uvicorn main:app --host 127.0.0.1 --port 8012 --reload
"""

from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import auth, chat, growth, guide, health, qa, resources, talent, training, user, voice
from app.core.logger import setup_logging
from app.db.models import ContentItem
from app.db.session import get_session_factory, init_db
from app.services.catalog_import import import_catalog

logger = setup_logging("jnao")


def _seed_catalog_if_empty() -> None:
    session = get_session_factory()()
    try:
        count = session.scalar(select(func.count()).select_from(ContentItem)) or 0
        if count == 0:
            inserted = import_catalog(session)
            logger.info(f"音频目录自动导入 {inserted} 条")
    except Exception as e:
        logger.warning(f"音频目录导入跳过: {e}")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _seed_catalog_if_empty()
    yield


app = FastAPI(title="JNAO API", version="0.3.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"--> {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"<-- {request.method} {request.url.path} {response.status_code}")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(talent.router)
app.include_router(chat.router)
app.include_router(guide.router)
app.include_router(voice.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(training.router)
app.include_router(resources.router)
app.include_router(qa.router)
app.include_router(growth.router)
