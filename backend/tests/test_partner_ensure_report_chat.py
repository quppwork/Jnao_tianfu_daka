"""合作方 ensure-report-chat：老库关联 → 本库测评 + token。"""

from unittest.mock import patch

from app.services import auth_service
from app.services.partner_report_chat_service import (
    ensure_report_chat,
    prepare_assessment_for_dayu_test,
    upsert_assessment_from_dayu,
)
from app.services.legacy_dayu_service import build_report_json_from_dayu_row


def test_build_report_json_prefers_column_talent():
    report = build_report_json_from_dayu_row(
        {
            "talent": "思者",
            "check_talent": "思德",
            "results": '{"AttributeJs": {"学者": 10, "思者": 90}}',
        }
    )
    assert report["talent"] == "思者"
    assert report["check_talent"] == "思德"
    assert report["AttributeJs"]["思者"] == 90


def test_upsert_and_ensure_report_chat(db_session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900002201",
        nickname="嵌入家长",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    db_session.commit()

    dayu_row = {
        "id": 90001,
        "uid": 10086,
        "test_type": 1,
        "answer": "1" * 35,
        "talent": "思者",
        "check_talent": "思德",
        "results": '{"results": {"Talent": {"desp": "测试解读"}, "Ability": []}}',
    }
    row = upsert_assessment_from_dayu(
        db_session, child_user_id=parent.id, dayu_row=dayu_row
    )
    assert row.id > 0
    assert row.test_type == 0
    assert row.jnao_record_id == "dayu_tr:90001"
    assert row.talent_primary == "思者"

    parent_legacy = {
        "id": 1,
        "user_id": 10086,
        "ai_user_id": parent.id,
        "mobile": "13900002201",
        "nickname": "嵌入家长",
    }
    with (
        patch(
            "app.services.partner_report_chat_service.fetch_parent_user_by_wx_id",
            return_value=parent_legacy,
        ),
        patch(
            "app.services.partner_report_chat_service.fetch_test_result",
            return_value=dayu_row,
        ),
        patch(
            "app.services.partner_report_chat_service.update_parent_ai_link",
        ) as upd,
    ):
        out = ensure_report_chat(db_session, wx_user_id=10086, test_result_id=90001)
    assert out["user_id"] == parent.id
    assert out["assessment_id"] == row.id
    assert out["access_token"]
    assert "assessment_id=" in out["embed_url"]
    assert upd.called


def test_prepare_by_dayu_id_for_logged_in_user(db_session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900002202",
        nickname="嵌入家长二",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    db_session.commit()
    dayu_row = {
        "id": 90002,
        "uid": 10087,
        "test_type": 1,
        "answer": "0" * 35,
        "talent": "赢者",
        "check_talent": "赢思",
        "results": "{}",
    }
    with (
        patch(
            "app.services.partner_report_chat_service.fetch_parent_user_by_ai_id",
            return_value={"user_id": 10087, "ai_user_id": parent.id},
        ),
        patch(
            "app.services.partner_report_chat_service.fetch_test_result",
            return_value=dayu_row,
        ),
    ):
        out = prepare_assessment_for_dayu_test(
            db_session, user_id=parent.id, dayu_test_result_id=90002
        )
    assert out["assessment_id"] > 0
    assert out["talent_primary"] == "赢者"
    assert out["wx_user_id"] == 10087
