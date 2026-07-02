#!/usr/bin/env python3
"""一次性数据迁移：老 training_progress → 新 v2.0 结构

用法：
  本地:  python scripts/migrate_state_v2.py
  Docker: docker compose -f docker-compose.prod.yml exec backend python migrate_state_v2.py

安全：只改 profile_json.training_progress，不影响其他字段
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Docker 容器内 /app 即 backend；本地从仓库根或 backend 目录均可运行
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = _HERE if os.path.isfile(os.path.join(_HERE, "main.py")) else os.path.join(_HERE, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

if not os.getenv("DATABASE_URL"):
    load_dotenv(os.path.join(_BACKEND, ".env"), override=True)
    _root_env = os.path.abspath(os.path.join(_BACKEND, "..", ".env.production"))
    if os.path.isfile(_root_env):
        load_dotenv(_root_env, override=True)

from sqlalchemy import select

from app.db.models import ChildUser
from app.db.session import get_session_factory, init_db
from app.services.child_training_state import _default_state


def migrate() -> None:
    init_db()
    db = get_session_factory()()
    try:
        users = db.scalars(select(ChildUser)).all()
        migrated = 0
        skipped = 0

        for user in users:
            pj = user.profile_json if isinstance(user.profile_json, dict) else {}
            old_state = pj.get("training_progress")

            if not old_state:
                pj["training_progress"] = _default_state()
                user.profile_json = pj
                migrated += 1
                continue

            if "overall_tier" in old_state:
                skipped += 1
                continue

            old_skills = old_state.get("skills") or {}
            new_state = _default_state()

            for skill_name, old_sd in old_skills.items():
                if skill_name in new_state["skills"] and isinstance(old_sd, dict):
                    new_state["skills"][skill_name]["oss_stage"] = int(
                        old_sd.get("stage", new_state["skills"][skill_name]["oss_stage"])
                    )
                    new_state["skills"][skill_name]["oss_part"] = int(
                        old_sd.get("part", new_state["skills"][skill_name]["oss_part"])
                    )

            new_state["training_days"] = int(old_state.get("training_days", 0))
            new_state["training_day_anchor"] = old_state.get("training_day_anchor")
            new_state["last_settled_plan_date"] = old_state.get("last_settled_plan_date")

            pj["training_progress"] = new_state
            user.profile_json = pj
            migrated += 1

        db.commit()
        print(f"OK: {migrated} users migrated, {skipped} already v2.0, {len(users)} total")
    except Exception as e:
        db.rollback()
        print(f"FAIL: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
