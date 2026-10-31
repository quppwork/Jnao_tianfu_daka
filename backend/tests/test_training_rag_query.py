"""训练页 RAG query 构建"""

from app.services.training_rag_query import build_training_rag_query


def test_build_training_rag_query_includes_talent_and_items():
    q = build_training_rag_query(
        talent_primary="学者",
        lesson_title="影像追忆",
        item_titles=["极速运算", "影像追忆"],
        yesterday_summary="昨日完成了影像追忆打卡",
    )
    assert "学者" in q
    assert "影像追忆" in q
    assert "极速运算" in q
    assert "昨日" in q


def test_build_training_rag_query_fallback():
    assert build_training_rag_query() == "今日训练方法与注意事项"
