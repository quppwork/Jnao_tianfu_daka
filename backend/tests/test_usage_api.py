"""GET /api/usage/summary"""

from fastapi.testclient import TestClient

from app.db.models import UpstreamUsageEvent
from app.services.usage_recorder import resolve_billing_parent_id


class TestUsageSummaryApi:
    def test_summary_empty(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/usage/summary?user_id={uid}")
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == uid
        assert data["me"]["total_tokens"] == 0
        assert data["display_total_tokens"] == 0

    def test_summary_after_record(self, client: TestClient, registered_user, db_session):
        uid = registered_user["child_user_id"]
        bp = resolve_billing_parent_id(db_session, uid)
        db_session.add(
            UpstreamUsageEvent(
                user_id=uid,
                billing_parent_id=bp,
                provider="doubao",
                feature="qa",
                model="test-model",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                call_count=1,
                ok=1,
            )
        )
        db_session.commit()

        res = client.get(f"/api/usage/summary?user_id={uid}")
        assert res.status_code == 200
        data = res.json()
        assert data["me"]["total_tokens"] == 150
        assert data["me"]["call_count"] == 1
        assert data["display_total_tokens"] == 150
        providers = {p["provider"]: p for p in data["me"]["by_provider"]}
        assert providers["doubao"]["total_tokens"] == 150
