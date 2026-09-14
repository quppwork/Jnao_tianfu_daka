"""算力中心 — 家长账本（会员额度 + 充值余额）与家计 token 汇总。

点（points）：产品侧额度单位（对话/测评扣点）。
token：上游 LLM/百炼实际消耗，记在 upstream_usage_event。
换算：默认 1000 token ≈ 1 点（展示会员额度占用；正式扣费可后续按功能价目表）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, CreditAccount, UpstreamUsageEvent

CST = ZoneInfo("Asia/Shanghai")

# 1000 upstream tokens ≈ 1 算力点（展示用）
TOKENS_PER_POINT = 1000

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

    row = db.execute(
        select(
            func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
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

    return {
        "billing_parent_id": pid,
        "period_yyyy_mm": period,
        "prompt_tokens": int(row[0] or 0),
        "completion_tokens": int(row[1] or 0),
        "total_tokens": int(row[2] or 0),
        "call_count": int(row[3] or 0),
        "event_count": int(row[4] or 0),
        "by_user": [
            {
                "user_id": int(r[0]) if r[0] is not None else None,
                "total_tokens": int(r[1] or 0),
                "call_count": int(r[2] or 0),
                "event_count": int(r[3] or 0),
            }
            for r in by_user_rows
        ],
        "all_time_total_tokens": int(all_time.get("total_tokens") or 0),
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
        "pay_enabled": False,
        "pay_hint": "支付通道即将开放，当前可查看家计用量与额度规划",
    }
