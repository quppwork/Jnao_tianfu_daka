#!/usr/bin/env python3
"""从老库同步 wx_member 到 jnao_daka.wx_member_snapshot（委托 backend/tools）"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "backend" / "tools" / "sync_wx_member_snapshot.py"
raise SystemExit(subprocess.call([sys.executable, str(TARGET)]))
