"""Resolve backend/root/export paths for local repo and Docker (/app)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def project_roots(tools_file: str | Path) -> tuple[Path, Path]:
    """Return (BACKEND, ROOT).

    从脚本位置向上找带 main.py + app/ 的目录（兼容 tools/ 与 tools/wework/）。

    - 本地仓库: backend/tools[/wework]/xxx.py → BACKEND=backend, ROOT=仓库根
    - Docker 镜像: /app/tools[/wework]/xxx.py → BACKEND=ROOT=/app
    """
    here = Path(tools_file).resolve().parent
    backend: Path | None = None
    for p in [here, *here.parents]:
        if (p / "main.py").is_file() and (p / "app").is_dir():
            backend = p
            break
    if backend is None:
        raise RuntimeError(f"找不到 backend 根目录（需含 main.py 与 app/）: {tools_file}")
    # 仓库根有 backend/ 子目录；Docker 镜像 WORKDIR=/app，没有这层
    if (backend.parent / "backend").is_dir():
        return backend, backend.parent
    return backend, backend


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
