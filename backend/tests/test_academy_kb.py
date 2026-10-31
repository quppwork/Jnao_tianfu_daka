"""短剧库只服务天赋学院；认知来自全局图。"""

import pytest

from app.agents.academy.kb import academy_kb, clip_notes, drama_notes
from app.agents.academy.world import character_knowledge, clear_world_cache
from app.services.kb_registry import get_kb_registry


def test_short_drama_ids_stay_out_of_guide_sources():
    get_kb_registry.cache_clear()
    reg = get_kb_registry()
    assert reg.get("short_drama") is None
    kb = academy_kb()
    # 百炼学院库暂空：只走本地全局图
    assert kb["index_id"] == ""
    assert kb["aid"] == ""


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


def test_character_knowledge_respects_cutoff():
    clear_world_cache()
    e13 = character_knowledge("jiahui", cutoff="E13")
    assert "五兽桩" in e13
    assert "蒙眼" not in e13
    assert "黄巢" not in e13
    e14 = character_knowledge("jiahui", cutoff="E14")
    assert "蒙眼" in e14 or "圆形" in e14 or "眼罩" in e14
    assert "黄巢" not in e14
    eh01 = character_knowledge("jiahui", cutoff="EH01")
    assert "黄巢" in eh01 or "种姓" in eh01
    assert "五兽桩" not in eh01
    assert "蒙眼" not in eh01


@pytest.mark.asyncio
async def test_drama_notes_uses_world_graph(monkeypatch):
    monkeypatch.setattr("app.agents.academy.kb.academy_kb", lambda: {"index_id": "", "aid": ""})
    clear_world_cache()
    notes = await drama_notes(
        names=["王家慧"],
        episode_id="E13",
        episode_title="E13 五兽桩",
        user_text="总结这一集",
        character_key="jiahui",
        knowledge_cutoff="E13",
    )
    assert "五兽桩" in notes or "涌泉" in notes or "桩" in notes


@pytest.mark.asyncio
async def test_drama_notes_e14_includes_mood(monkeypatch):
    monkeypatch.setattr("app.agents.academy.kb.academy_kb", lambda: {"index_id": "", "aid": ""})
    clear_world_cache()
    notes = await drama_notes(
        names=["王家慧"],
        episode_id="E14",
        episode_title="蒙上眼睛之后",
        user_text="戴上眼罩你怕不怕黑？",
        character_key="jiahui",
        knowledge_cutoff="E14",
    )
    assert "眼罩" in notes or "圆形" in notes or "红" in notes
    assert "心情" in notes or "震住" in notes
