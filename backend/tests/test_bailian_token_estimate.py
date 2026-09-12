"""百炼 RAG Token 估算单测（对齐官方计费说明逻辑）"""

from app.services.bailian.token_estimate import (
    estimate_retrieve_tokens,
    estimate_text_tokens,
)


def test_estimate_text_tokens_cjk():
    assert estimate_text_tokens("你好世界") == 4
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("   ") == 0


def test_estimate_retrieve_query_only_no_rerank():
    est = estimate_retrieve_tokens(
        "什么是天赋",
        chunk_texts=["很长的切片内容" * 10],
        enable_reranking=False,
        prelim_top_k=50,
    )
    assert est.query_embed_tokens == estimate_text_tokens("什么是天赋")
    assert est.rerank_tokens == 0
    assert est.total_tokens == est.query_embed_tokens


def test_estimate_retrieve_with_rerank_uses_prelim_not_final():
    # 最终只返回 2 条，但计费按 prelim=50
    chunks = ["切片甲" * 20, "切片乙" * 20]
    est = estimate_retrieve_tokens(
        "查询",
        chunk_texts=chunks,
        enable_reranking=True,
        prelim_top_k=50,
    )
    avg = est.avg_chunk_tokens
    assert est.rerank_tokens == 50 * avg
    assert est.total_tokens == est.query_embed_tokens + est.rerank_tokens


def test_estimate_multi_index_multiplies():
    est1 = estimate_retrieve_tokens("你好", enable_reranking=True, prelim_top_k=10, index_count=1)
    est4 = estimate_retrieve_tokens("你好", enable_reranking=True, prelim_top_k=10, index_count=4)
    assert est4.query_embed_tokens == est1.query_embed_tokens * 4
    assert est4.rerank_tokens == est1.rerank_tokens * 4
