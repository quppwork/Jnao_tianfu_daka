"""家长查看绑定孩子的测试记录。"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import TalentAssessment
from app.services import auth_service, assessment_service


def test_parent_assessment_history_api(client: TestClient, db_session: Session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900009901",
        nickname="家长测记",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    child = auth_service.register_child(
        db_session,
        parent_phone="13900009901",
        nickname="孩子测记",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    auth_service.bind_parent_child(db_session, parent.id, child.id)
    db_session.add(
        TalentAssessment(
            child_user_id=child.id,
            jnao_record_id="r-parent-hist",
            answer_bitstring="1" * 35,
            test_type=1,
            talent_primary="学者",
            talent_tag="xuezhe",
            talent_code=1,
            report_json={},
            assessed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    res = client.get(f"/api/parent/assessments/history?user_id={parent.id}")
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert len(items) >= 1
    assert items[0]["talent_primary"] == "学者"
    assert items[0]["child_nickname"] == "孩子测记"
    assert items[0]["mode"] == "kid"


def test_list_assessments_for_parent_helper(db_session: Session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900009902",
        nickname="家长辅",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    child = auth_service.register_child(
        db_session,
        parent_phone="13900009902",
        nickname="孩子辅",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    auth_service.bind_parent_child(db_session, parent.id, child.id)
    db_session.add(
        TalentAssessment(
            child_user_id=child.id,
            test_type=0,
            talent_primary="思者",
            assessed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    items = assessment_service.list_assessments_for_parent(db_session, parent.id)
    assert len(items) == 1
    assert items[0]["mode"] == "adult"
    assert items[0]["child_id"] == child.id


def test_student_cannot_use_parent_assessment_history(
    client: TestClient, db_session: Session
):
    child = auth_service.register_child(
        db_session,
        parent_phone="13900009903",
        nickname="学生越权",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    db_session.commit()
    res = client.get(f"/api/parent/assessments/history?user_id={child.id}")
    assert res.status_code == 403
