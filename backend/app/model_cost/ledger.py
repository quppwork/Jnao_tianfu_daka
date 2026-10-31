"""UsageLedger — CostRecorder 的默认实现，委托 usage_recorder 落库。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.model_cost.features import feature_label, normalize_feature
from app.model_cost.protocols import CostEvent, CostSummary
from app.model_cost.rates import RateCard, default_rate_card


class UsageLedger:
    def __init__(self, *, rate_card: RateCard | None = None) -> None:
        self._rates = rate_card or default_rate_card()

    def bind_feature(self, feature: str) -> None:
        from app.services.usage_recorder import bind_usage_feature

        bind_usage_feature(normalize_feature(feature))

    def record(self, event: CostEvent) -> None:
        from app.services.usage_recorder import record_usage

        feat = normalize_feature(event.feature)
        record_usage(
            provider=event.provider,
            api=event.api,
            model=event.model,
            feature=feat,
            user_id=event.user_id,
            request_id=event.request_id,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            total_tokens=event.total_tokens or (
                event.prompt_tokens + event.completion_tokens
            ),
            call_count=event.call_count,
            doc_count=event.doc_count,
            metric_kind=event.metric_kind,
            estimated=event.estimated,
            ok=event.ok,
        )

    def summarize(
        self,
        *,
        user_id: int | None = None,
        billing_parent_id: int | None = None,
        db: Session | None = None,
    ) -> list[CostSummary]:
        from app.db.models import UpstreamUsageEvent
        from app.db.session import get_session_factory

        own = False
        session = db
        if session is None:
            session = get_session_factory()()
            own = True
        try:
            q = select(
                UpstreamUsageEvent.feature,
                UpstreamUsageEvent.provider,
                func.coalesce(func.sum(UpstreamUsageEvent.total_tokens), 0),
                func.coalesce(func.sum(UpstreamUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(UpstreamUsageEvent.completion_tokens), 0),
                func.coalesce(func.sum(UpstreamUsageEvent.call_count), 0),
            ).where(UpstreamUsageEvent.ok == 1)
            if user_id is not None:
                q = q.where(UpstreamUsageEvent.user_id == int(user_id))
            if billing_parent_id is not None:
                q = q.where(
                    UpstreamUsageEvent.billing_parent_id == int(billing_parent_id)
                )
            q = q.group_by(UpstreamUsageEvent.feature, UpstreamUsageEvent.provider)
            rows = session.execute(q).all()
        finally:
            if own:
                session.close()

        by_feat: dict[str, dict[str, Any]] = {}
        for feature, provider, total, prompt, completion, calls in rows:
            feat = normalize_feature(feature)
            bucket = by_feat.setdefault(
                feat,
                {
                    "total_tokens": 0,
                    "call_count": 0,
                    "estimated_cost_milli": 0,
                    "by_provider": [],
                },
            )
            rate = self._rates.resolve(str(provider or ""), None)
            milli = rate.estimate_milli(
                prompt_tokens=int(prompt or 0),
                completion_tokens=int(completion or 0),
            )
            bucket["total_tokens"] += int(total or 0)
            bucket["call_count"] += int(calls or 0)
            bucket["estimated_cost_milli"] += milli
            bucket["by_provider"].append(
                {
                    "provider": str(provider or ""),
                    "total_tokens": int(total or 0),
                    "call_count": int(calls or 0),
                    "estimated_cost_milli": milli,
                }
            )

        out: list[CostSummary] = []
        for feat, data in sorted(by_feat.items()):
            out.append(
                CostSummary(
                    feature=feat,
                    label=feature_label(feat),
                    total_tokens=int(data["total_tokens"]),
                    call_count=int(data["call_count"]),
                    estimated_cost_milli=int(data["estimated_cost_milli"]),
                    by_provider=list(data["by_provider"]),
                )
            )
        return out


_LEDGER: UsageLedger | None = None


def get_cost_recorder() -> UsageLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = UsageLedger()
    return _LEDGER
