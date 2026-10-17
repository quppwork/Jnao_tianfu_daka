"""TDD: 成人报告天赋解答 HTTP 接口。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.services.assessment_service import save_assessment


def _adult_assessment(db: Session, child_user_id: int) -> TalentAssessment:
    return save_assessment(
        db,
        child_user_id=child_user_id,
        jnao_record_id="adult-chat-1",
        answer_bitstring="1" * 35,
        test_type=0,
        report={"talent": "学者", "create_time": "2026-10-17"},
    )


class TestReportTalentChatApi:
    def test_history_returns_opening_without_messages(
        self, client: TestClient, registered_user, db_session: Session
    ):
        uid = registered_user["child_user_id"]
        row = _adult_assessment(db_session, uid)
        res = client.get(f"/api/talent/assessment/{row.id}/chat?user_id={uid}")
        assert res.status_code == 200
        body = res.json()
        assert body["assessment_id"] == row.id
        assert body["opening"]
        assert body["messages"] == []
        assert body["test_type"] == 0

    def test_child_report_chat_forbidden(
        self, client: TestClient, registered_user, db_session: Session
    ):
        uid = registered_user["child_user_id"]
        row = save_assessment(
            db_session,
            child_user_id=uid,
            jnao_record_id="child-chat-1",
            answer_bitstring="0" * 35,
            test_type=1,
            report={"talent": "学者"},
        )
        res = client.get(f"/api/talent/assessment/{row.id}/chat?user_id={uid}")
        assert res.status_code == 403

    def test_post_chat_persists_via_runtime(
        self, client: TestClient, registered_user, db_session: Session
    ):
        uid = registered_user["child_user_id"]
        row = _adult_assessment(db_session, uid)
        with patch(
            "app.runtime.run_turn",
            new=AsyncMock(
                return_value={
                    "reply": "按库内练法，先从阅读起步。",
                    "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
                    "rag_used": True,
                    "llm_calls": 2,
                    "status": "completed",
                }
            ),
        ):
            res = client.post(
                f"/api/talent/assessment/{row.id}/chat?user_id={uid}",
                json={"content": "学者怎么练"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["assistant"]["content"]
        assert body["user"]["content"] == "学者怎么练"
        assert body["refused"] is False

        hist = client.get(f"/api/talent/assessment/{row.id}/chat?user_id={uid}")
        assert hist.status_code == 200
        msgs = hist.json()["messages"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_missing_assessment_404(self, client: TestClient, registered_user):
        uid = registered_user["child_user_id"]
        res = client.get(f"/api/talent/assessment/999999/chat?user_id={uid}")
        assert res.status_code == 404
