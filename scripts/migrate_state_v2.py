#!/usr/bin/env python3
"""入口转发 — 实际逻辑在 backend/migrate_state_v2.py"""

import os
import runpy
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET = os.path.join(ROOT, "backend", "migrate_state_v2.py")

if not os.path.isfile(TARGET):
    print(f"FAIL: not found {TARGET}")
    sys.exit(1)

runpy.run_path(TARGET, run_name="__main__")
