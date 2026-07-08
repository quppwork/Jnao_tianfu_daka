"""应用元信息 — 版本探测与热更新"""

import os

from fastapi import APIRouter

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/version")
def app_version():
    return {
        "version": os.getenv("JNAO_APP_VERSION", "0.3.0"),
        "build_id": os.getenv("JNAO_BUILD_ID", "dev"),
    }
