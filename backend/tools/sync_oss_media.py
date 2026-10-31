"""兼容入口：请改用 backend/tools/ops/sync_oss_media.py"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "ops" / "sync_oss_media.py"), run_name="__main__")
