"""接入层 · 用量/费用查询（Fee 数据的 HTTP 出口）。

不算价、不写 event；读 model_cost / credit_service 已落库快照。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_authenticated_user, get_db
from app.db.models import ChildUser, UpstreamUsageEvent
from app.model_cost.rates import milli_cent_to_yuan
from app.services.credit_service import build_wallet_payload
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


@router.get("/wallet")
def usage_wallet(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """算力中心：家长+孩子本月 token 汇总 + 会员额度/充值余额账本。"""
    return build_wallet_payload(db, user_id)


@router.get("/by-feature")
def usage_by_feature(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """各 Agent 板块模型费用汇总（低耦合 model_cost 组件）。"""
    from app.model_cost import get_cost_recorder
    from app.services.usage_recorder import resolve_billing_parent_id

    ledger = get_cost_recorder()
    from app.model_cost.rates import milli_cent_to_yuan

    def _row(s):
        return {
            "feature": s.feature,
            "label": s.label,
            "total_tokens": s.total_tokens,
            "call_count": s.call_count,
            "estimated_cost_milli": s.estimated_cost_milli,
            "cost_yuan": round(milli_cent_to_yuan(s.estimated_cost_milli), 6),
            "by_provider": s.by_provider,
        }

    me = [_row(s) for s in ledger.summarize(user_id=user_id, db=db)]
    billing_parent_id = resolve_billing_parent_id(db, user_id)
    household = None
    if billing_parent_id:
        household = [
            _row(s)
            for s in ledger.summarize(billing_parent_id=billing_parent_id, db=db)
        ]
    return {
        "user_id": user_id,
        "billing_parent_id": billing_parent_id,
        "me": me,
        "household": household,
    }


@router.get("/events")
def usage_events(
    user_id: int = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    scope: str = Query("household", pattern="^(me|household)$"),
):
    """最近调用明细（含人民币快照）— 本地看板 / 算力页下钻。"""
    user = db.get(ChildUser, user_id)
    role = (user.role if user else None) or "student"
    billing_parent_id = resolve_billing_parent_id(db, user_id)

    q = select(UpstreamUsageEvent).where(UpstreamUsageEvent.ok == 1)
    if scope == "me" or role != "parent":
        q = q.where(UpstreamUsageEvent.user_id == int(user_id))
    elif billing_parent_id:
        q = q.where(UpstreamUsageEvent.billing_parent_id == int(billing_parent_id))
    else:
        q = q.where(UpstreamUsageEvent.user_id == int(user_id))

    rows = db.scalars(q.order_by(UpstreamUsageEvent.id.desc()).limit(int(limit))).all()
    items = []
    for r in rows:
        milli = int(r.cost_milli_cent or 0)
        items.append(
            {
                "id": int(r.id),
                "created_at": r.created_at.isoformat(sep=" ", timespec="seconds")
                if r.created_at
                else None,
                "user_id": r.user_id,
                "billing_parent_id": r.billing_parent_id,
                "provider": r.provider,
                "model": r.model,
                "feature": r.feature,
                "prompt_tokens": int(r.prompt_tokens or 0),
                "completion_tokens": int(r.completion_tokens or 0),
                "total_tokens": int(r.total_tokens or 0),
                "cost_milli_cent": milli,
                "cost_yuan": round(milli_cent_to_yuan(milli), 6),
                "rate_version": r.rate_version,
                "estimated": bool(r.estimated),
                "stream": bool(r.stream),
            }
        )
    return {
        "user_id": user_id,
        "role": role,
        "scope": scope,
        "billing_parent_id": billing_parent_id,
        "items": items,
    }
