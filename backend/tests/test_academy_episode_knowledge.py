"""分集 knowledge.yaml：加载、隔离注入、与 pack 解耦。"""

from __future__ import annotations

import pytest

from app.agents.academy.knowledge import (
    clear_knowledge_cache,
    compose_episode_notes,
    format_episode_notes,
    get_knowledge,
    knowledge_synopsis,
)
from app.agents.academy.kb import drama_notes
from app.agents.academy.packs import clear_pack_cache, pack_synopsis
from app.agents.academy.turn import prepare_turn, turn_instruction
from app.agents.academy.world import clear_world_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_knowledge_cache()
    clear_pack_cache()
    clear_world_cache()
    yield
    clear_knowledge_cache()
    clear_pack_cache()
    clear_world_cache()


def test_knowledge_yaml_loaded_per_episode():
    e13 = get_knowledge("E13")
    e14 = get_knowledge("E14")
    assert e13 is not None and not e13.empty
    assert e14 is not None and not e14.empty
    assert "站桩" in e13.synopsis or "五兽" in e13.synopsis
    assert "眼罩" in e14.synopsis or "蒙眼" in e14.synopsis
    assert "第一扇门" in e13.cannot_know
    assert e13.character_beats.get("chenxue")
    assert e14.character_beats.get("jiahui")


def test_format_notes_is_grounding_not_script():
    know = get_knowledge("E13")
    notes = format_episode_notes(know, character_key="chenxue")
    assert "本集梗概" in notes
    assert "你本集视角" in notes
    assert "勿提" in notes or "本集未知" in notes


def test_pack_synopsis_prefers_knowledge():
    text = pack_synopsis("E13")
    assert text
    assert text == knowledge_synopsis(get_knowledge("E13"))


@pytest.mark.asyncio
async def test_compose_local_only_when_no_bailian(monkeypatch):
    class _EmptyRemote:
        async def fetch_notes(self, **_kwargs):
            return ""

    notes = await compose_episode_notes(
        episode_id="E13",
        episode_title="五兽桩",
        user_text="这一集讲了什么",
        character_key="jiahui",
        knowledge_cutoff="E13",
        remote=_EmptyRemote(),
    )
    assert "涌泉" in notes or "站桩" in notes or "五兽" in notes
    # 黄巢只应出现在「勿提」边界，不应当成本集情节
    assert "勿提" in notes or "本集未知" in notes
    assert "博物馆" not in notes


@pytest.mark.asyncio
async def test_drama_notes_includes_local_knowledge(monkeypatch):
    monkeypatch.setattr(
        "app.agents.academy.kb.academy_kb",
        lambda: {"index_id": "", "aid": ""},
    )
    notes = await drama_notes(
        names=["陈雪"],
        episode_id="E13",
        episode_title="五兽桩",
        user_text="总结这一集",
        character_key="chenxue",
        knowledge_cutoff="E13",
    )
    assert "桩" in notes or "定" in notes
    assert "博物馆" not in notes
    assert "勿提" in notes or "本集未知" in notes or "第一扇门" in notes


def test_turn_instruction_open_style_and_boundary():
    ctx = prepare_turn(user_text="这一集讲了什么", episode_id="E13")
    assert ctx.episode_id == "E13"
    hint = turn_instruction(ctx, character_key="chenxue", index=0)
    assert "即兴" in hint or "真人同学" in hint
    assert "边界" in hint or "勿提" in hint or "第一扇门" in hint


def test_greet_avoids_train_script():
    ctx = prepare_turn(user_text="你们好", episode_id="E13")
    hint = turn_instruction(ctx, character_key="dani", index=0)
    assert ctx.skill == "greet"
    assert "训练要领" in hint or "剧情口号" in hint
