"""百炼 RAG Token 估算 — 对齐官方知识库计费说明（非账单精确值）。

官方：https://help.aliyun.com/zh/model-studio/billing-for-knowledge-base

检索阶段模型费用大致：
  1) Query 向量化：按用户输入 Token
  2) Rerank（可选）：初步召回总切片数 × 平均切片 Token
     （按初步召回量，不是最终返回条数）

本模块在 API 不返回 usage 时做本地估算，落库须带 estimated=1。
规格费（元/库/小时）不在此估算。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


# 官方计费示例中的默认切片均长（无返回文本可估时回退）
_DEFAULT_CHUNK_TOKENS = 500


def estimate_text_tokens(text: str | None) -> int:
    """粗估文本 Token（非 DashScope 官方分词器）。

    中文场景经验：约 1 汉字 ≈ 1 token；非汉字按 ~4 字符 1 token。
    仅用于看板估算，对账以云账单为准。
    """
    s = (text or "").strip()
    if not s:
        return 0
    cjk = 0
    other = 0
    for ch in s:
        o = ord(ch)
        if (
            0x4E00 <= o <= 0x9FFF
            or 0x3400 <= o <= 0x4DBF
            or 0xF900 <= o <= 0xFAFF
            or 0x3000 <= o <= 0x303F
        ):
            cjk += 1
        elif ch.isspace():
            continue
        else:
            other += 1
    return max(1, cjk + max(0, (other + 3) // 4))


def _avg_chunk_tokens(chunk_texts: Sequence[str] | None) -> int:
    texts = [t for t in (chunk_texts or []) if (t or "").strip()]
    if not texts:
        return _DEFAULT_CHUNK_TOKENS
    total = sum(estimate_text_tokens(t) for t in texts)
    return max(1, (total + len(texts) - 1) // len(texts))


@dataclass(frozen=True)
class BailianRagTokenEstimate:
    """一次检索的估算拆分。"""

    query_embed_tokens: int
    rerank_tokens: int
    prelim_chunk_count: int
    avg_chunk_tokens: int
    rerank_enabled: bool

    @property
    def total_tokens(self) -> int:
        return int(self.query_embed_tokens) + int(self.rerank_tokens)


def estimate_retrieve_tokens(
    query: str,
    *,
    chunk_texts: Sequence[str] | None = None,
    enable_reranking: bool = True,
    prelim_top_k: int = 50,
    index_count: int = 1,
) -> BailianRagTokenEstimate:
    """按官方检索计费逻辑估算。

    - query_embed_tokens：Query 向量化
    - rerank_tokens：prelim_top_k × avg_chunk_tokens（开启重排时）
    - index_count：多库检索时官方按库数倍增（N 库 × N）
    """
    n_index = max(1, int(index_count or 1))
    q_tok = estimate_text_tokens(query) * n_index
    avg = _avg_chunk_tokens(chunk_texts)
    prelim = max(0, int(prelim_top_k or 0))
    if enable_reranking and prelim > 0:
        rerank = prelim * avg * n_index
    else:
        rerank = 0
        prelim = 0
    return BailianRagTokenEstimate(
        query_embed_tokens=q_tok,
        rerank_tokens=rerank,
        prelim_chunk_count=prelim,
        avg_chunk_tokens=avg,
        rerank_enabled=bool(enable_reranking and prelim > 0),
    )
