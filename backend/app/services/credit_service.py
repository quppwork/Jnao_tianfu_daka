"""能力层 · 算力额度账本（Fee 的「可不可用」门闸数据，非 Agent）。

点：产品额度；token/¥：上游实耗快照（upstream_usage_event）。
接入层 API 调用 require_credit；价目与计量仍在 model_cost。
CREDIT_ENFORCE=1 时额度用尽且余额为 0 → HTTP 402。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, CreditAccount, UpstreamUsageEvent

CST = ZoneInfo("Asia/Shanghai")

# 1000 upstream tokens ≈ 1 算力点（展示用）
TOKENS_PER_POINT = 1000


def credit_enforce_enabled() -> bool:
    return (os.getenv("CREDIT_ENFORCE") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

MEMBERSHIP_PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "code": "free",
        "name": "免费体验",
        "monthly_quota_points": 1000,
        "price_cents": 0,
        "blurb": "每月 1,000 点算力 · 体验对话与基础功能",
    },
    "lite": {
        "code": "lite",
        "name": "轻享会员",
        "monthly_quota_points": 1000,
        "price_cents": 4900,
        "blurb": "每月 1,000 点算力 · 约 30 次天赋测试/对话",
    },
    "plus": {
        "code": "plus",
        "name": "进阶会员",
        "monthly_quota_points": 2000,
        "price_cents": 9900,
        "blurb": "每月 2,000 点算力 · 训练计划+数据分析全开",
    },
    "pro": {
        "code": "pro",
        "name": "专业会员",
        "monthly_quota_points": 5000,
        "price_cents": 19900,
        "blurb": "每月 5,000 点算力 · 全家多孩子共享",
    },
    "flagship": {
        "code": "flagship",
        "name": "旗舰会员",
        "monthly_quota_points": 12000,
        "price_cents": 69900,
        "blurb": "每月 12,000 点算力 · 导师优先响应+线下课折扣",
    },
}

TOPUP_PACKS: list[dict[str, Any]] = [
    {"code": "pack_50", "price_cents": 520, "points": 50, "label": "体验包 · 50点"},
    {"code": "pack_100", "price_cents": 990, "points": 100, "label": "加油包 · 100点"},
    {"code": "pack_320", "price_cents": 2880, "points": 320, "label": "超值包 · 320点"},
    {"code": "pack_600", "price_cents": 4990, "points": 600, "label": "畅享包 · 600点"},
    {"code": "pack_1300", "price_cents": 9900, "points": 1300, "label": "家庭包 · 1300点"},
    {"code": "pack_6000", "price_cents": 39900, "points": 6000, "label": "年度包 · 6000点"},
]


def _now_cst() -> datetime:
    return datetime.now(CST)


def _period_yyyy_mm(now: datetime | None = None) -> str:
    n = now or _now_cst()
    return n.strftime("%Y-%m")


def tokens_to_points(total_tokens: int) -> int:
    t = max(0, int(total_tokens or 0))
    return t // TOKENS_PER_POINT


def credit_snapshot(db: Session, user_id: int) -> dict[str, Any]:
    """当前操作者所属家长账本快照（用于拦截与钱包）。"""
    from app.services.usage_recorder import resolve_billing_parent_id

    uid = int(user_id)
    billing_parent_id = resolve_billing_parent_id(db, uid) or uid
    account = get_or_create_credit_account(db, billing_parent_id)
    month = sum_tokens_for_billing_parent_month(
        db, billing_parent_id, period_yyyy_mm=account.period_yyyy_mm or _period_yyyy_mm()
    )
    month_tokens = int(month.get("total_tokens") or 0)
    points_used = tokens_to_points(month_tokens)
    quota = int(account.monthly_quota_points or 0)
    remaining = max(0, quota - points_used)
    balance_cents = int(account.balance_cents or 0)
    return {
        "billing_parent_id": billing_parent_id,
        "plan_code": account.plan_code,
        "period_yyyy_mm": account.period_yyyy_mm,
        "monthly_quota_points": quota,
        "monthly_used_points": points_used,
        "monthly_remaining_points": remaining,
        "balance_cents": balance_cents,
        "ok": remaining > 0 or balance_cents > 0,
    }


def require_credit(db: Session, user_id: int) -> dict[str, Any]:
    """对话入口调用：额度不足则 402。CREDIT_ENFORCE=0 时只返回快照不拦截。"""
    snap = credit_snapshot(db, user_id)
    if not credit_enforce_enabled():
        return snap
    if snap.get("ok"):
        return snap
    raise HTTPException(
        status_code=402,
        detail={
            "code": "credit_exhausted",
            "message": "本月算力已用完，请充值或升级会员后再试",
            "billing_parent_id": snap.get("billing_parent_id"),
            "monthly_quota_points": snap.get("monthly_quota_points"),
            "monthly_used_points": snap.get("monthly_used_points"),
            "balance_cents": snap.get("balance_cents"),
        },
    )


def get_or_create_credit_account(db: Session, owner_user_id: int) -> CreditAccount:
    uid = int(owner_user_id)
    row = db.scalar(select(CreditAccount).where(CreditAccount.owner_user_id == uid))
    period = _period_yyyy_mm()
    if row is None:
        free = MEMBERSHIP_PLANS["free"]
        row = CreditAccount(
            owner_user_id=uid,
            balance_cents=0,
            plan_code="free",
            monthly_quota_points=int(free["monthly_quota_points"]),
            period_yyyy_mm=period,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    # 跨月：刷新计费月标记（正式扣点账本后可在此写 reset ledger）
    if (row.period_yyyy_mm or "") != period:
        row.period_yyyy_mm = period
        plan = MEMBERSHIP_PLANS.get(row.plan_code) or MEMBERSHIP_PLANS["free"]
        row.monthly_quota_points = int(plan["monthly_quota_points"])
        db.commit()
        db.refresh(row)
    return row


def sum_tokens_for_billing_parent_month(
    db: Session,
    parent_id: int,
    *,
    period_yyyy_mm: str | None = None,
) -> dict[str, Any]:
    """本月（CST）家计 token 合计 + 分账户。"""
    from app.services.usage_recorder import sum_tokens_for_billing_parent

    pid = int(parent_id)
    period = period_yyyy_mm or _period_yyyy_mm()
    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1, tzinfo=CST).replace(tzinfo=None)
    if month == 12:
        end = datetime(year + 1, 1, 1).replace(tzinfo=None)
    else:
        end = datetime(year, month + 1, 1).replace(tzinfo=None)

    from app.model_cost.rates import milli_cent_to_yuan

    row = db.execute(
        select(
            func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
            func.coalesce(func.sum(UpstreamUsageEvent.cost_milli_cent), 0),
        ).where(
            UpstreamUsageEvent.billing_parent_id == pid,
            UpstreamUsageEvent.ok == 1,
            UpstreamUsageEvent.created_at >= start,
            UpstreamUsageEvent.created_at < end,
        )
    ).one()

    by_user_rows = db.execute(
        select(
            UpstreamUsageEvent.user_id,
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
            func.coalesce(func.sum(UpstreamUsageEvent.cost_milli_cent), 0),
        )
        .where(
            UpstreamUsageEvent.billing_parent_id == pid,
            UpstreamUsageEvent.ok == 1,
            UpstreamUsageEvent.created_at >= start,
            UpstreamUsageEvent.created_at < end,
        )
        .group_by(UpstreamUsageEvent.user_id)
    ).all()

    # 全量家计（不过滤月份）作对照
    all_time = sum_tokens_for_billing_parent(db, pid)
    milli = int(row[5] or 0)

    return {
        "billing_parent_id": pid,
        "period_yyyy_mm": period,
        "prompt_tokens": int(row[0] or 0),
        "completion_tokens": int(row[1] or 0),
        "total_tokens": int(row[2] or 0),
        "call_count": int(row[3] or 0),
        "event_count": int(row[4] or 0),
        "cost_milli_cent": milli,
        "cost_yuan": round(milli_cent_to_yuan(milli), 6),
        "by_user": [
            {
                "user_id": int(r[0]) if r[0] is not None else None,
                "total_tokens": int(r[1] or 0),
                "call_count": int(r[2] or 0),
                "event_count": int(r[3] or 0),
                "cost_milli_cent": int(r[4] or 0),
                "cost_yuan": round(milli_cent_to_yuan(int(r[4] or 0)), 6),
            }
            for r in by_user_rows
        ],
        "all_time_total_tokens": int(all_time.get("total_tokens") or 0),
        "all_time_cost_yuan": all_time.get("cost_yuan"),
    }


def _label_users(db: Session, by_user: list[dict]) -> list[dict]:
    ids = [int(x["user_id"]) for x in by_user if x.get("user_id")]
    names: dict[int, ChildUser] = {}
    if ids:
        for u in db.scalars(select(ChildUser).where(ChildUser.id.in_(ids))).all():
            names[int(u.id)] = u
    out = []
    for item in by_user:
        uid = item.get("user_id")
        u = names.get(int(uid)) if uid is not None else None
        role = (u.role if u else None) or "unknown"
        out.append(
            {
                **item,
                "nickname": (u.nickname if u else None) or ("家长" if role == "parent" else "学员"),
                "role": role,
            }
        )
    return out


def build_wallet_payload(db: Session, user_id: int) -> dict[str, Any]:
    """算力中心页聚合：家计 token + 账本额度。"""
    from app.services.usage_recorder import resolve_billing_parent_id, sum_tokens_for_user

    uid = int(user_id)
    user = db.get(ChildUser, uid)
    role = (user.role if user else None) or "student"
    billing_parent_id = resolve_billing_parent_id(db, uid) or uid

    account = get_or_create_credit_account(db, billing_parent_id)
    month = sum_tokens_for_billing_parent_month(
        db, billing_parent_id, period_yyyy_mm=account.period_yyyy_mm or _period_yyyy_mm()
    )
    me = sum_tokens_for_user(db, uid)

    month_tokens = int(month.get("total_tokens") or 0)
    points_used = tokens_to_points(month_tokens)
    quota = int(account.monthly_quota_points or 0)
    remaining = max(0, quota - points_used)
    remain_pct = int(round(remaining / quota * 100)) if quota > 0 else 0
    plan = MEMBERSHIP_PLANS.get(account.plan_code) or MEMBERSHIP_PLANS["free"]

    return {
        "user_id": uid,
        "role": role,
        "billing_parent_id": billing_parent_id,
        "tokens_per_point": TOKENS_PER_POINT,
        "account": {
            "plan_code": account.plan_code,
            "plan_name": plan.get("name"),
            "monthly_quota_points": quota,
            "monthly_used_points": points_used,
            "monthly_remaining_points": remaining,
            "remain_pct": remain_pct,
            "balance_cents": int(account.balance_cents or 0),
            "balance_yuan": round(int(account.balance_cents or 0) / 100.0, 2),
            "period_yyyy_mm": account.period_yyyy_mm,
        },
        "usage": {
            "me": me,
            "family_month": {
                **month,
                "by_user": _label_users(db, list(month.get("by_user") or [])),
            },
            "display_total_tokens": int(month.get("all_time_total_tokens") or month_tokens),
            "display_month_tokens": month_tokens,
        },
        "catalog": {
            "membership": list(MEMBERSHIP_PLANS.values()),
            "topup": TOPUP_PACKS,
        },
        "credit_enforce": credit_enforce_enabled(),
        "pay_enabled": False,
        "pay_hint": "支付通道即将开放；可先打开 CREDIT_ENFORCE=1 做额度硬拦截",
    }
