#!/usr/bin/env python3
"""清空除管理员外的全部用户业务数据，便于重新注册测试。

保留：
  - child_user（role=admin）
  - content_item（课表目录）
  - wx_member_snapshot（微信会员镜像，只读对照）

默认仅预览（--dry-run）；确认后加 --apply 执行。

生产容器内示例:
  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \\
    python -m tools.reset_non_admin_data --dry-run

  docker compose -f docker-compose.prod.yml --env-file .env.production exec -T backend \\
    python -m tools.reset_non_admin_data --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(BACKEND.parent / ".env.production", override=False)

from sqlalchemy import delete, select

from app.db.models import (
    ChildUser,
    DakaMember,
    GuideMessage,
    GuideSession,
    ParentChildBind,
    ParentWechatBind,
    QaMessage,
    QaSession,
    TalentAssessment,
    TalentAssessmentArchive,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
    UserSession,
)
from app.db.session import get_session_factory
from app.services import auth_service


def _non_admin_user_ids(db) -> list[int]:
    return list(
        db.scalars(
            select(ChildUser.id).where(ChildUser.role != auth_service.ROLE_ADMIN)
        ).all()
    )


def preview(db) -> dict:
    user_ids = _non_admin_user_ids(db)
    users = db.scalars(
        select(ChildUser).where(ChildUser.role != auth_service.ROLE_ADMIN)
    ).all()
    summary = {
        "non_admin_users": len(user_ids),
        "sample_users": [
            {
                "id": u.id,
                "role": u.role,
                "phone": u.parent_phone,
                "nickname": u.nickname,
                "login_name": u.login_name,
            }
            for u in users[:20]
        ],
    }
    if not user_ids:
        return summary

    plan_ids = list(
        db.scalars(select(TrainingPlan.id).where(TrainingPlan.child_user_id.in_(user_ids))).all()
    )
    qa_ids = list(
        db.scalars(select(QaSession.id).where(QaSession.child_user_id.in_(user_ids))).all()
    )
    guide_ids = list(
        db.scalars(select(GuideSession.id).where(GuideSession.child_user_id.in_(user_ids))).all()
    )

    def _n(model, *where):
        return len(db.scalars(select(model.id).where(*where)).all())

    summary["counts"] = {
        "user_session": _n(UserSession, UserSession.user_id.in_(user_ids)),
        "daka_member": _n(DakaMember, DakaMember.parent_id.in_(user_ids)),
        "parent_wechat_bind": _n(ParentWechatBind, ParentWechatBind.parent_id.in_(user_ids)),
        "parent_child_bind": len(
            db.scalars(
                select(ParentChildBind.id).where(
                    (ParentChildBind.parent_id.in_(user_ids))
                    | (ParentChildBind.child_id.in_(user_ids))
                )
            ).all()
        ),
        "talent_assessment": _n(TalentAssessment, TalentAssessment.child_user_id.in_(user_ids)),
        "training_plan": len(plan_ids),
        "training_record": _n(TrainingRecord, TrainingRecord.child_user_id.in_(user_ids)),
        "qa_session": len(qa_ids),
        "guide_session": len(guide_ids),
    }
    return summary


def apply_reset(db) -> dict:
    user_ids = _non_admin_user_ids(db)
    if not user_ids:
        return {"deleted_users": 0}

    plan_ids = list(db.scalars(select(TrainingPlan.id).where(TrainingPlan.child_user_id.in_(user_ids))).all())
    qa_ids = list(db.scalars(select(QaSession.id).where(QaSession.child_user_id.in_(user_ids))).all())
    guide_ids = list(db.scalars(select(GuideSession.id).where(GuideSession.child_user_id.in_(user_ids))).all())

    stats: dict[str, int] = {}

    if guide_ids:
        r = db.execute(delete(GuideMessage).where(GuideMessage.session_id.in_(guide_ids)))
        stats["guide_message"] = r.rowcount or 0
        r = db.execute(delete(GuideSession).where(GuideSession.id.in_(guide_ids)))
        stats["guide_session"] = r.rowcount or 0

    if qa_ids:
        r = db.execute(delete(QaMessage).where(QaMessage.session_id.in_(qa_ids)))
        stats["qa_message"] = r.rowcount or 0
        r = db.execute(delete(QaSession).where(QaSession.id.in_(qa_ids)))
        stats["qa_session"] = r.rowcount or 0

    r = db.execute(delete(TrainingRecord).where(TrainingRecord.child_user_id.in_(user_ids)))
    stats["training_record"] = r.rowcount or 0
    r = db.execute(delete(TrainingWindow).where(TrainingWindow.child_user_id.in_(user_ids)))
    stats["training_window"] = r.rowcount or 0

    if plan_ids:
        r = db.execute(delete(TrainingItem).where(TrainingItem.plan_id.in_(plan_ids)))
        stats["training_item"] = r.rowcount or 0
        r = db.execute(delete(TrainingPlan).where(TrainingPlan.id.in_(plan_ids)))
        stats["training_plan"] = r.rowcount or 0

    r = db.execute(delete(TalentAssessmentArchive).where(TalentAssessmentArchive.child_user_id.in_(user_ids)))
    stats["talent_assessment_archive"] = r.rowcount or 0
    r = db.execute(delete(TalentAssessment).where(TalentAssessment.child_user_id.in_(user_ids)))
    stats["talent_assessment"] = r.rowcount or 0

    r = db.execute(delete(UserSession).where(UserSession.user_id.in_(user_ids)))
    stats["user_session"] = r.rowcount or 0
    r = db.execute(delete(ParentWechatBind).where(ParentWechatBind.parent_id.in_(user_ids)))
    stats["parent_wechat_bind"] = r.rowcount or 0
    r = db.execute(
        delete(ParentChildBind).where(
            (ParentChildBind.parent_id.in_(user_ids)) | (ParentChildBind.child_id.in_(user_ids))
        )
    )
    stats["parent_child_bind"] = r.rowcount or 0
    r = db.execute(delete(DakaMember).where(DakaMember.parent_id.in_(user_ids)))
    stats["daka_member"] = r.rowcount or 0

    r = db.execute(delete(ChildUser).where(ChildUser.id.in_(user_ids)))
    stats["child_user"] = r.rowcount or 0

    db.commit()
    stats["deleted_users"] = len(user_ids)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="清空除管理员外的用户数据")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不删除")
    parser.add_argument("--apply", action="store_true", help="执行删除")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("请指定 --dry-run 或 --apply")

    factory = get_session_factory()
    with factory() as db:
        if args.dry_run:
            summary = preview(db)
            print("=== 预览（不会删除）===")
            for k, v in summary.items():
                print(f"{k}: {v}")
            return 0

        stats = apply_reset(db)
        print("=== 已清空 ===")
        for k, v in stats.items():
            print(f"{k}: {v}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
