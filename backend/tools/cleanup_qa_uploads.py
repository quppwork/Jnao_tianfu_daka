"""兼容入口：请改用 backend/tools/cleanup/cleanup_qa_uploads.py"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "cleanup" / "cleanup_qa_uploads.py"), run_name="__main__")
