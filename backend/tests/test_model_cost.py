"""模型费用组件 — 费率估算与按 feature 汇总。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, UpstreamUsageEvent
from app.model_cost import (
    AgentFeature,
    CostEvent,
    UsageLedger,
    default_rate_card,
    feature_label,
)


def test_feature_labels():
    assert feature_label(AgentFeature.REPORT_TALENT) == "报告天赋解答"
    assert feature_label(AgentFeature.GUIDE) == "首页引导"


def test_rate_estimate():
    card = default_rate_card()
    rate = card.resolve("doubao", "ep-x")
    assert rate.estimate_milli(prompt_tokens=1000, completion_tokens=1000) == 2 + 6


def test_ledger_summarize_by_feature():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = ChildUser(parent_phone="13900000001", nickname="u", role="student", password_hash="x")
    db.add(user)
    db.flush()
    db.add(
        UpstreamUsageEvent(
            provider="doubao",
            api="chat",
            feature=AgentFeature.REPORT_TALENT,
            user_id=user.id,
            billing_parent_id=user.id,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            call_count=1,
            ok=1,
        )
    )
    db.add(
        UpstreamUsageEvent(
            provider="bailian",
            api="retrieve",
            feature=AgentFeature.RAG,
            user_id=user.id,
            billing_parent_id=user.id,
            prompt_tokens=20,
            completion_tokens=0,
            total_tokens=20,
            call_count=1,
            ok=1,
        )
    )
    db.commit()

    ledger = UsageLedger()
    rows = ledger.summarize(user_id=user.id, db=db)
    feats = {r.feature: r for r in rows}
    assert AgentFeature.REPORT_TALENT in feats
    assert feats[AgentFeature.REPORT_TALENT].total_tokens == 150
    assert AgentFeature.RAG in feats
    db.close()


def test_cost_event_record_delegates(monkeypatch):
    seen = {}

    def fake_record_usage(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(
        "app.services.usage_recorder.record_usage", fake_record_usage
    )
    ledger = UsageLedger()
    ledger.record(
        CostEvent(
            provider="doubao",
            feature=AgentFeature.QA,
            api="chat",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    assert seen["feature"] == AgentFeature.QA
    assert seen["total_tokens"] == 15
