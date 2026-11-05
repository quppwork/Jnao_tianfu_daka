"""定期裁剪测评历史：首条确认天赋常留 + 其余合计最多 10 条。

用法（容器/宝塔）:
  cd /data/wwwroot/jnao_daka
  docker compose -f docker-compose.prod.yml exec backend \\
    python -m scripts.prune_assessments

可选: --keep 10  --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune talent_assessment over limit")
    parser.add_argument("--keep", type=int, default=None, help="合计保留条数（默认 10）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计超限用户，不删除",
    )
    args = parser.parse_args()

    from sqlalchemy import func, select

    from app.db.models import TalentAssessment
    from app.db.session import get_session_factory, init_db
    from app.services import assessment_service as svc

    keep = args.keep if args.keep is not None else svc.ASSESSMENT_HISTORY_KEEP
    init_db()
    db = get_session_factory()()
    try:
        if args.dry_run:
            subq = (
                select(
                    TalentAssessment.child_user_id,
                    func.count().label("cnt"),
                )
                .group_by(TalentAssessment.child_user_id)
                .having(func.count() > keep)
            )
            rows = db.execute(subq).all()
            print(f"dry-run keep={keep} over_limit_users={len(rows)}")
            for uid, cnt in rows[:50]:
                print(f"  child_user_id={uid} count={cnt}")
            return 0

        out = svc.prune_all_assessments_over_limit(db, keep=keep)
        print(
            f"prune keep={keep} users_pruned={out['users_pruned']} deleted={out['deleted']}"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
