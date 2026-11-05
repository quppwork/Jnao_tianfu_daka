"""TDD: 成人报告天赋解答 HTTP 接口。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.harness.types import ToolResult
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

    def test_post_chat_persists_via_knowledge_qa(
        self, client: TestClient, registered_user, db_session: Session
    ):
        uid = registered_user["child_user_id"]
        row = _adult_assessment(db_session, uid)
        tool = ToolResult(
            ok=True,
            name="knowledge_qa",
            data={"ok": True, "reply": "按库内练法，先从阅读起步。", "aid": "aid-x"},
        )
        with patch("app.harness.runtime.call_tool", new=AsyncMock(return_value=tool)):
            res = client.post(
                f"/api/talent/assessment/{row.id}/chat?user_id={uid}",
                json={"content": "学者怎么练"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["assistant"]["content"] == "按库内练法，先从阅读起步。"
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

    def test_stream_endpoint_emits_sse_and_persists(
        self, client: TestClient, registered_user, db_session: Session
    ):
        uid = registered_user["child_user_id"]
        row = _adult_assessment(db_session, uid)

        async def _gen(*_args, **_kwargs):
            yield ("token", "第一步")
            yield ("token", "是阅读。")
            yield (
                "result",
                SimpleNamespace(reply="第一步是阅读。", aid="aid-x", request_id="r1"),
            )

        with patch(
            "app.services.bailian.knowledge_chat.knowledge_chat_stream", new=_gen
        ), patch(
            "app.services.kb_policy.knowledge_qa_aid", return_value="aid-x"
        ), patch(
            "app.services.bailian.config.load_bailian_config",
            return_value=MagicMock(),
        ):
            res = client.post(
                f"/api/talent/assessment/{row.id}/chat/stream?user_id={uid}",
                json={"content": "学者怎么练"},
            )
        assert res.status_code == 200
        body = res.text
        assert '"type": "token"' in body or '"type":"token"' in body
        assert "[DONE]" in body

        hist = client.get(f"/api/talent/assessment/{row.id}/chat?user_id={uid}")
        msgs = hist.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["content"] == "第一步是阅读。"
