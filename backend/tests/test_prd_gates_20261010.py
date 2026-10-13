"""产品需求 2026-10：咨询规则 / 学业规划闸 / 学院边界。"""

from __future__ import annotations

from app.harness.llm_catalog import (
    DAYU_FALLBACK,
    TALENT_FALLBACK,
    consult_persona_system,
)


def test_consult_dayu_and_talent_rules():
    dayu = consult_persona_system("dayu")
    assert "大宇入口" in dayu or "可以答" in dayu
    assert DAYU_FALLBACK[:12] in dayu
    assert "留言板仅用于审核" in dayu

    talent = consult_persona_system("sizhe")
    assert "五者天赋顾问" in talent
    assert TALENT_FALLBACK[:12] in talent
    assert "贴类型标签" in talent or "贴类型" in talent


def test_academic_plan_gate_rejects_empty(db_session):
    from app.services.academic_plan_service import check_academic_plan_ready
    from app.services.auth_service import register_child

    user = register_child(db_session, parent_phone="13900139991", nickname="规划闸童")
    gate = check_academic_plan_ready(db_session, user.id)
    assert gate["ok"] is False
    assert gate["reason"] == "incomplete_plan"
    assert gate.get("missing")
    assert "学业规划" in (gate.get("student_hint") or "")


def test_academy_boundary_in_say_user_message():
    from app.agents.academy.harness import _say_user_message

    msg = _say_user_message(
        "频道刚打开",
        "",
        [],
        None,
        drama_notes="今天练了五兽桩",
        user_ask="下一集结局是什么？",
        scene_context="训练场",
    )
    assert "不剧透" in msg or "未发布" in msg
    assert "占位兜底" in msg or "还不知道" in msg
