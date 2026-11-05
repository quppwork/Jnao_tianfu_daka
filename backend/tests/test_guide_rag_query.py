"""引导页 RAG 检索问句构建。"""

from app.services.guide_rag_query import (
    build_guide_rag_query,
    extract_guide_skill_focus,
    is_guide_practice_method_question,
)


def test_extract_skill_super_brain():
    assert extract_guide_skill_focus("超脑阅读具体怎么练习啊") == "超脑阅读"


def test_extract_skill_kai_kou_qiao():
    assert extract_guide_skill_focus("开口窍怎么练习") == "开口窍"


def test_practice_method_question():
    assert is_guide_practice_method_question("超脑阅读具体怎么练习啊")
    assert is_guide_practice_method_question("开口窍怎么练习")
    assert not is_guide_practice_method_question("学者天赋是什么")


def test_build_query_prefers_method_steps():
    q = build_guide_rag_query("超脑阅读具体怎么练习啊")
    assert "超脑阅读" in q
    assert "训练方法" in q
    assert "练习步骤" in q


def test_build_query_kai_kou_qiao():
    q = build_guide_rag_query("开口窍怎么练习")
    assert "开口窍" in q
    assert "训练方法" in q


def test_build_query_non_practice_uses_message():
    q = build_guide_rag_query("学者天赋有什么特点")
    assert "学者" in q
    assert "训练方法" not in q
