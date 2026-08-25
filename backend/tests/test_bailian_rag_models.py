"""百炼 RagResult / 配置冒烟"""

from app.services.bailian.config import load_bailian_config
from app.services.bailian.models import RagNode, RagResult


def test_rag_result_block_and_sources():
    result = RagResult(
        nodes=[
            RagNode(text="学者擅长逻辑", score=0.9, doc_name="天赋特征"),
            RagNode(text="训练建议多练阅读", score=0.8, doc_name="天赋特征"),
            RagNode(text="其他", score=0.7, doc_name="翻箱进化之书"),
        ],
        mode="retrieve",
        query="学者",
    )
    assert result.node_count == 3
    assert result.sources == ["天赋特征", "翻箱进化之书"]
    assert "[1]" in result.rag_block
    assert "学者擅长逻辑" in result.rag_block
    pub = result.to_public_dict()
    assert pub["mode"] == "retrieve"
    assert pub["node_count"] == 3


def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-test")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
    cfg = load_bailian_config()
    assert cfg.workspace_id == "ws-test"
    assert cfg.index_id == "idx-test"
    assert cfg.access_key_id == "ak"
    assert cfg.mode == "retrieve"
    assert cfg.enable_reranking is True
