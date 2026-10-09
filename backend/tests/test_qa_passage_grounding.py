"""答疑多轮：OCR 原文落会话 + 定位纠错意图。"""

from app.agents.qa.memory import (
    load_session_memory,
    load_session_passage,
    save_session_memory,
    save_session_passage,
)
from app.agents.qa.prompt_builder import build_learner_context_block
from app.agents.qa.runner import looks_like_location_correction
from app.agents.qa.subjects.registry import get_subject_agent
from app.harness.llm_catalog import QA_PROFILE_TOOLS


def test_location_correction_detects_user_feedback():
    assert looks_like_location_correction("你说的这些段落和行数有点不太对啊")
    assert looks_like_location_correction("定位错了吧")
    assert not looks_like_location_correction("这道阅读理解怎么做")


def test_session_passage_survives_memory_save(db_session, registered_user):
    from app.services import qa_service

    uid = registered_user["child_user_id"]
    session = qa_service.create_session(db_session, uid, "外语")
    save_session_passage(
        session,
        image_id="abc123",
        ocr_text="Paragraph 1\nHello world\nParagraph 2\nGoodbye",
    )
    save_session_memory(
        db_session,
        session,
        {"rolling_summary": "学员:问阅读；老师:讲定位"},
    )
    db_session.commit()

    image_id, ocr = load_session_passage(session)
    assert image_id == "abc123"
    assert "Hello world" in (ocr or "")
    mem = load_session_memory(session)
    assert "问阅读" in mem["rolling_summary"]


def test_learner_context_marks_ocr_as_ground_truth():
    block = build_learner_context_block(ocr_preview="The hotel is across the street.")
    assert "本会话题目原文" in block
    assert "禁止编造" in block
    assert "across the street" in block


def test_english_agent_requires_passage_grounding():
    agent = get_subject_agent("外语")
    assert "禁止编造" in agent.answer_style or "编造" in agent.answer_style
    assert "qa_reload_passage" in agent.answer_style
    assert "qa_reload_passage" in QA_PROFILE_TOOLS
