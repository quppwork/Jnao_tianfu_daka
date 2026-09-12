"""学科答疑 — 多轮检索问句测试（单库 x1micrdmjq）。"""

from app.services.qa_kb_query import (
    build_qa_kb_rounds,
    extract_qa_skill_focus,
    pick_qa_kb_source_key,
)


def test_pick_source_always_talent_doc_in_single_mode():
    assert pick_qa_kb_source_key("数学怎么学") == "talent_doc"
    assert pick_qa_kb_source_key("开口窍怎么练") == "talent_doc"


def test_extract_skill():
    assert extract_qa_skill_focus("超脑阅读怎么练") == "超脑阅读"


def test_rounds_how_to_study_same_index():
    rounds = build_qa_kb_rounds("数学怎么学", subject="数学")
    assert len(rounds) >= 1
    assert all(r["source_key"] == "talent_doc" for r in rounds)
    assert "学习方法" in rounds[0]["query"] or "系统训练" in rounds[0]["query"]


def test_rounds_skill_practice_same_index():
    rounds = build_qa_kb_rounds("开口窍怎么练才有效", subject="语文")
    assert rounds[0]["source_key"] == "talent_doc"
    assert "开口窍" in rounds[0]["query"]
    assert "训练方法" in rounds[0]["query"]
    assert all(r["source_key"] == "talent_doc" for r in rounds)
