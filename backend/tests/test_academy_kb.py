"""短剧库只服务天赋学院，不进引导页选库。"""

from app.agents.academy.kb import academy_kb, clip_notes
from app.services.kb_registry import get_kb_registry


def test_short_drama_ids_stay_out_of_guide_sources():
    get_kb_registry.cache_clear()
    reg = get_kb_registry()
    assert reg.get("short_drama") is None
    kb = academy_kb()
    assert kb["index_id"] == "nv8orv5dh5"
    assert kb["aid"] == "aid-caa8c7be748c45d6a29a27b42d57525a"


def test_clip_notes_drops_later_episodes_and_wounds():
    chunks = [
        "E13 五兽桩。善雨只看心定不定。",
        "E16 738。门还没开。",
        "父亲胃癌住院，病房里喂饭。",
        "李寞话少，句尾截断。",
    ]
    text = clip_notes(chunks, "E13")
    assert "五兽桩" in text
    assert "738" not in text
    assert "胃癌" not in text
    assert "句尾截断" in text
