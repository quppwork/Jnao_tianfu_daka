"""兼容入口：请改用 backend/tools/wework/sync_wx_member_snapshot.py"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "wework" / "sync_wx_member_snapshot.py"), run_name="__main__")
