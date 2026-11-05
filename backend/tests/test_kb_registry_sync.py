"""kb_registry_sync 纯函数测试。"""

from app.services.kb_registry_sync import merge_tags, _stem_to_tags


def test_stem_to_tags():
    tags = _stem_to_tags("火箭提分营")
    assert "火箭提分营" in tags
    assert _stem_to_tags("a") == []
    # 带分隔符时拆分
    parts = _stem_to_tags("火箭提分营-产品说明")
    assert "火箭提分营" in parts or "火箭提分营-产品说明" in parts


def test_merge_tags_adds_new():
    merged = merge_tags(["天赋", "五者"], ["火箭提分营", "天赋"])
    assert "天赋" in merged
    assert "五者" in merged
    assert "火箭提分营" in merged
