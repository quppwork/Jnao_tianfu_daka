"""Resolve backend/root/export paths for local repo and Docker (/app)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def project_roots(tools_file: str | Path) -> tuple[Path, Path]:
    """Return (BACKEND, ROOT).

    - 本地仓库: backend/tools/xxx.py → BACKEND=backend, ROOT=仓库根
    - Docker 镜像: /app/tools/xxx.py → BACKEND=ROOT=/app
    """
    tools = Path(tools_file).resolve().parent
    backend = tools.parent
    # Docker: main.py 在 /app，且没有上层 backend/ 目录
    if (backend / "main.py").exists() and not (backend.parent / "backend").is_dir():
        return backend, backend
    return backend, backend.parent


def export_dir(backend: Path, root: Path) -> Path:
    if backend == root:
        # 容器内写到持久卷 /app/data
        return backend / "data" / "qywx_export"
    return root / "docs" / "export"


def load_env(backend: Path, root: Path) -> None:
    load_dotenv(backend / ".env", override=False)
    load_dotenv(root / ".env", override=False)
    load_dotenv(root / ".env.production", override=False)
    # 容器里通常已由 compose env_file 注入，无需文件
    _ = os.environ
