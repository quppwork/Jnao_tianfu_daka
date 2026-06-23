"""JNAO Backend — 集中平台 API

启动: uvicorn main:app --host 127.0.0.1 --port 8011 --reload
"""

from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import talent, chat, health, guide, voice
from app.core.logger import setup_logging

logger = setup_logging("jnao")

app = FastAPI(title="JNAO API", version="0.2.0")

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
