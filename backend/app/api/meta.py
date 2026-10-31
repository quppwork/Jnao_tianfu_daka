"""应用元信息 — 版本探测、维护模式、发版标志"""

import os

from fastapi import APIRouter

from app.core.runtime import runtime_flags

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/version")
def app_version():
    return {
        "version": os.getenv("JNAO_APP_VERSION", "0.3.0"),
        "build_id": os.getenv("JNAO_BUILD_ID", "dev"),
        **runtime_flags(),
    }
