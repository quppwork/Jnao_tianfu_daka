#!/usr/bin/env python3
"""一次性数据迁移：老 training_progress → 新 v2.0 结构

用法：python scripts/migrate_state_v2.py
安全：只改 profile_json.training_progress，不影响其他字段
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from sqlalchemy import select, update
from app.db.models import ChildUser
from app.db.session import get_session_factory, init_db
from app.services.child_training_state import _default_state


def migrate():
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
                # No state yet — init with v2.0 default
                pj["training_progress"] = _default_state()
                user.profile_json = pj
                migrated += 1
                continue

            if "overall_tier" in old_state:
                # Already v2.0
                skipped += 1
                continue

            # Migrate from v1.0
            old_skills = old_state.get("skills") or {}
            new_state = _default_state()

            # Preserve existing OSS positions where available
            for skill_name, old_sd in old_skills.items():
                if skill_name in new_state["skills"]:
                    if isinstance(old_sd, dict):
                        new_state["skills"][skill_name]["oss_stage"] = int(old_sd.get("stage", new_state["skills"][skill_name]["oss_stage"]))
                        new_state["skills"][skill_name]["oss_part"] = int(old_sd.get("part", new_state["skills"][skill_name]["oss_part"]))

            # Preserve training days
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
