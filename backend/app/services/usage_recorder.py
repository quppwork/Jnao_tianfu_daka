"""上游用量记录 — 按 user_id 分计；billing_parent_id 供家长汇总。

明细：每个操作者（家长本人或某个孩子）单独一行。
汇总：SUM WHERE billing_parent_id = 家长ID（含家长自己 + 名下孩子）。
充值扣余额：后置，本期只计数不扣费。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.biz_log import biz_event, get_request_id, get_user_id
from app.core.logger import get_logger

logger = get_logger("usage")

_feature: ContextVar[str] = ContextVar("usage_feature", default="")


def bind_usage_feature(feature: str | None) -> None:
    _feature.set((feature or "").strip())


def get_usage_feature() -> str:
    return (_feature.get() or "").strip()


def reset_usage_feature() -> None:
    _feature.set("")


def _parse_usage_dict(usage: dict | None) -> tuple[int, int, int]:
    if not usage or not isinstance(usage, dict):
        return 0, 0, 0
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion) or 0)
    if total <= 0 and (prompt > 0 or completion > 0):
        total = prompt + completion
    return max(0, prompt), max(0, completion), max(0, total)


def resolve_billing_parent_id(db: Session, user_id: int | None) -> int | None:
    """孩子 → 其家长；家长或未绑定 → 自身。"""
    if user_id is None or int(user_id) <= 0:
        return None
    uid = int(user_id)
    from app.db.models import ParentChildBind

    parent_id = db.scalar(
        select(ParentChildBind.parent_id).where(ParentChildBind.child_id == uid)
    )
    return int(parent_id) if parent_id else uid


def record_usage(
    *,
    provider: str,
    api: str | None = None,
    model: str | None = None,
    feature: str | None = None,
    user_id: int | None = None,
    request_id: str | None = None,
    usage: dict | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    call_count: int = 1,
    doc_count: int = 0,
    metric_kind: str = "tokens",
    stream: bool = False,
    estimated: bool = False,
    ok: bool = True,
    db: Session | None = None,
) -> None:
    """写日志并尽量落库；失败不影响主业务。"""
    p_tok, c_tok, t_tok = _parse_usage_dict(usage)
    if prompt_tokens is not None:
        p_tok = max(0, int(prompt_tokens))
    if completion_tokens is not None:
        c_tok = max(0, int(completion_tokens))
    if total_tokens is not None:
        t_tok = max(0, int(total_tokens))
    elif t_tok <= 0 and (p_tok or c_tok):
        t_tok = p_tok + c_tok

    uid = user_id if user_id is not None else get_user_id()
    feat = (feature or get_usage_feature() or "").strip() or None
    rid = (request_id or get_request_id() or "").strip() or None
    if rid == "-":
        rid = None

    biz_event(
        "upstream.usage",
        result="ok" if ok else "error",
        uid=uid,
        provider=provider,
        api=api or "-",
        model=model or "-",
        feature=feat or "-",
        metric=metric_kind,
        prompt=p_tok,
        completion=c_tok,
        total=t_tok,
        calls=call_count,
        docs=doc_count,
        stream=1 if stream else 0,
        estimated=1 if estimated else 0,
    )

    own_session = False
    session = db
    try:
        if session is None:
            from app.db.session import get_session_factory

            session = get_session_factory()()
            own_session = True

        billing_parent_id = resolve_billing_parent_id(session, uid)
        from app.db.models import UpstreamUsageEvent

        session.add(
            UpstreamUsageEvent(
                provider=str(provider)[:32],
                api=(api or None) and str(api)[:64],
                model=(model or None) and str(model)[:128],
                feature=feat and str(feat)[:64],
                user_id=uid,
                billing_parent_id=billing_parent_id,
                request_id=rid and str(rid)[:64],
                metric_kind=str(metric_kind or "tokens")[:16],
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                total_tokens=t_tok,
                call_count=max(0, int(call_count)),
                doc_count=max(0, int(doc_count)),
                stream=1 if stream else 0,
                estimated=1 if estimated else 0,
                ok=1 if ok else 0,
            )
        )
        session.commit()
    except Exception as e:
        logger.warning("record_usage persist failed: %s", e)
        try:
            if session is not None:
                session.rollback()
        except Exception:
            pass
    finally:
        if own_session and session is not None:
            try:
                session.close()
            except Exception:
                pass


def sum_tokens_by_user_ids(db: Session, user_ids: list[int]) -> dict[int, dict[str, Any]]:
    """批量：多个 user_id → 用量合计（缺省为 0）。"""
    from app.db.models import UpstreamUsageEvent

    ids = [int(x) for x in user_ids if x is not None]
    empty = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "call_count": 0,
        "event_count": 0,
    }
    out: dict[int, dict[str, Any]] = {uid: {**empty, "user_id": uid} for uid in ids}
    if not ids:
        return out
    rows = db.execute(
        select(
            UpstreamUsageEvent.user_id,
            func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        )
        .where(UpstreamUsageEvent.user_id.in_(ids), UpstreamUsageEvent.ok == 1)
        .group_by(UpstreamUsageEvent.user_id)
    ).all()
    for r in rows:
        uid = int(r[0])
        out[uid] = {
            "user_id": uid,
            "prompt_tokens": int(r[1] or 0),
            "completion_tokens": int(r[2] or 0),
            "total_tokens": int(r[3] or 0),
            "call_count": int(r[4] or 0),
            "event_count": int(r[5] or 0),
        }
    return out


def sum_tokens_by_billing_parent_ids(
    db: Session, parent_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """批量：多个 billing_parent_id → 家计用量合计。"""
    from app.db.models import UpstreamUsageEvent

    ids = [int(x) for x in parent_ids if x is not None]
    empty = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "call_count": 0,
        "event_count": 0,
    }
    out: dict[int, dict[str, Any]] = {pid: {**empty, "billing_parent_id": pid} for pid in ids}
    if not ids:
        return out
    rows = db.execute(
        select(
            UpstreamUsageEvent.billing_parent_id,
            func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        )
        .where(
            UpstreamUsageEvent.billing_parent_id.in_(ids),
            UpstreamUsageEvent.ok == 1,
        )
        .group_by(UpstreamUsageEvent.billing_parent_id)
    ).all()
    for r in rows:
        if r[0] is None:
            continue
        pid = int(r[0])
        out[pid] = {
            "billing_parent_id": pid,
            "prompt_tokens": int(r[1] or 0),
            "completion_tokens": int(r[2] or 0),
            "total_tokens": int(r[3] or 0),
            "call_count": int(r[4] or 0),
            "event_count": int(r[5] or 0),
        }
    return out


def usage_by_provider_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    from app.db.models import UpstreamUsageEvent

    rows = db.execute(
        select(
            UpstreamUsageEvent.provider,
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        )
        .where(UpstreamUsageEvent.user_id == int(user_id), UpstreamUsageEvent.ok == 1)
        .group_by(UpstreamUsageEvent.provider)
    ).all()
    return [
        {
            "provider": str(r[0]),
            "total_tokens": int(r[1] or 0),
            "call_count": int(r[2] or 0),
            "event_count": int(r[3] or 0),
        }
        for r in rows
    ]


def usage_by_provider_for_billing_parent(db: Session, parent_id: int) -> list[dict[str, Any]]:
    from app.db.models import UpstreamUsageEvent

    rows = db.execute(
        select(
            UpstreamUsageEvent.provider,
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        )
        .where(
            UpstreamUsageEvent.billing_parent_id == int(parent_id),
            UpstreamUsageEvent.ok == 1,
        )
        .group_by(UpstreamUsageEvent.provider)
    ).all()
    return [
        {
            "provider": str(r[0]),
            "total_tokens": int(r[1] or 0),
            "call_count": int(r[2] or 0),
            "event_count": int(r[3] or 0),
        }
        for r in rows
    ]


def sum_tokens_for_user(db: Session, user_id: int) -> dict[str, Any]:
    """单个账户（家长或某一个孩子）的用量合计。"""
    from app.db.models import UpstreamUsageEvent

    row = db.execute(
        select(
            func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        ).where(UpstreamUsageEvent.user_id == int(user_id), UpstreamUsageEvent.ok == 1)
    ).one()
    return {
        "user_id": int(user_id),
        "prompt_tokens": int(row[0] or 0),
        "completion_tokens": int(row[1] or 0),
        "total_tokens": int(row[2] or 0),
        "call_count": int(row[3] or 0),
        "event_count": int(row[4] or 0),
    }


def sum_tokens_for_billing_parent(db: Session, parent_id: int) -> dict[str, Any]:
    """结算用：家长本人 + 名下所有孩子（billing_parent_id）。"""
    from app.db.models import UpstreamUsageEvent

    pid = int(parent_id)
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
        )
    ).one()

    # 分账户明细（便于看板）
    by_user_rows = db.execute(
        select(
            UpstreamUsageEvent.user_id,
            func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            func.count(UpstreamUsageEvent.id),
        )
        .where(UpstreamUsageEvent.billing_parent_id == pid, UpstreamUsageEvent.ok == 1)
        .group_by(UpstreamUsageEvent.user_id)
    ).all()

    return {
        "billing_parent_id": pid,
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
    }
