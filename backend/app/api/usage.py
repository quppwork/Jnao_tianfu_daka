"""上游用量查询 — 供开发/算力条展示"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.db.models import ChildUser, UpstreamUsageEvent
from app.services.usage_recorder import (
    resolve_billing_parent_id,
    sum_tokens_for_billing_parent,
    sum_tokens_for_user,
)

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _by_provider(db: Session, *, user_id: int | None = None, billing_parent_id: int | None = None) -> list[dict]:
    q = select(
        UpstreamUsageEvent.provider,
        func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
        func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
        func.count(UpstreamUsageEvent.id),
    ).where(UpstreamUsageEvent.ok == 1)
    if user_id is not None:
        q = q.where(UpstreamUsageEvent.user_id == int(user_id))
    if billing_parent_id is not None:
        q = q.where(UpstreamUsageEvent.billing_parent_id == int(billing_parent_id))
    q = q.group_by(UpstreamUsageEvent.provider)
    rows = db.execute(q).all()
    return [
        {
            "provider": str(r[0]),
            "total_tokens": int(r[1] or 0),
            "call_count": int(r[2] or 0),
            "event_count": int(r[3] or 0),
        }
        for r in rows
    ]


@router.get("/summary")
def usage_summary(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """当前登录用户用量 + 所属家长账本汇总（开发可视化 / 算力条）。"""
    user = db.get(ChildUser, user_id)
    role = (user.role if user else None) or "student"
    me = sum_tokens_for_user(db, user_id)
    me["by_provider"] = _by_provider(db, user_id=user_id)

    billing_parent_id = resolve_billing_parent_id(db, user_id)
    billing = None
    if billing_parent_id:
        billing = sum_tokens_for_billing_parent(db, billing_parent_id)
        billing["by_provider"] = _by_provider(db, billing_parent_id=billing_parent_id)

    if role == "parent" and billing is not None:
        display_total = int(billing.get("total_tokens") or 0)
    else:
        display_total = int(me.get("total_tokens") or 0)

    return {
        "user_id": user_id,
        "role": role,
        "me": me,
        "billing": billing,
        # 顶栏主数字：家长看家计；学生看自己（旁边可再看家计）
        "display_total_tokens": display_total,
    }
