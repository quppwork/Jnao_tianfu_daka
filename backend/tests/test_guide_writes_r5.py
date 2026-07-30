# -*- coding: utf-8 -*-
"""R5：受控写白名单 + 确认卡 + 落库审计。"""

from app.agents.guide.student_memory import load_guide_memory
from app.agents.guide.writes import (
    WRITE_WHITELIST,
    execute_write,
    propose_write_confirms,
)
from app.services.auth_service import register_child


def test_propose_requires_save_intent():
    assert propose_write_confirms("我想练40分钟") == []
    acts = propose_write_confirms("帮我记下想练40分钟")
    assert len(acts) == 1
    assert acts[0]["type"] == "confirm"
    assert acts[0]["write_op"] == "save_preferred_minutes"
    assert acts[0]["args"]["minutes"] == 40


def test_propose_remind_skill():
    acts = propose_write_confirms("请记住下次多留意扫描速记弱项")
    assert acts and acts[0]["write_op"] == "save_remind_skill"
    assert acts[0]["args"]["skill"] == "扫描速记"


def test_execute_rejects_unknown_op(db_session):
    user = register_child(db_session, parent_phone="1390000r501", nickname="拒写")
    bad = execute_write(db_session, user.id, "hack_tier", {"tier": 9})
    assert bad["ok"] is False
    assert "hack_tier" not in WRITE_WHITELIST or bad["ok"] is False


def test_execute_preferred_minutes_and_audit(db_session):
    user = register_child(db_session, parent_phone="1390000r502", nickname="记时长")
    # 确认前不应已有 confirmed
    mem0 = load_guide_memory(db_session, user.id)
    assert mem0["preferences"].get("preferred_minutes_source") != "confirmed"

    r = execute_write(
        db_session, user.id, "save_preferred_minutes", {"minutes": 45}
    )
    assert r["ok"] is True
    mem = load_guide_memory(db_session, user.id)
    assert mem["preferences"]["preferred_minutes"] == 45
    assert mem["preferences"]["preferred_minutes_source"] == "confirmed"

    db_session.refresh(user)
    audit = (user.profile_json or {}).get("guide_write_audit") or []
    assert audit and audit[-1]["write_op"] == "save_preferred_minutes"
    assert audit[-1]["ok"] is True


def test_execute_remind_skill(db_session):
    user = register_child(db_session, parent_phone="1390000r503", nickname="记弱项")
    r = execute_write(
        db_session, user.id, "save_remind_skill", {"skill": "超脑阅读"}
    )
    assert r["ok"] is True
    mem = load_guide_memory(db_session, user.id)
    assert "超脑阅读" in mem["preferences"]["remind_skills"]


def test_confirm_api(client, user_ready_for_training):
    uid = user_ready_for_training
    # 拒绝非白名单
    bad = client.post(
        "/api/guide/confirm",
        json={"write_op": "submit_checkin", "args": {}},
        headers={"X-Child-User-Id": str(uid)},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/guide/confirm",
        json={"write_op": "save_preferred_minutes", "args": {"minutes": 30}},
        headers={"X-Child-User-Id": str(uid)},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json().get("ok") is True
    assert ok.json().get("preferred_minutes") == 30
