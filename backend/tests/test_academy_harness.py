"""学院 harness：解锁线、开场顺序、回复选人。不打真实大模型。"""

import asyncio

from app.agents.academy import harness


def test_unlock_needs_ninety_percent():
    assert harness.should_unlock(89) is False
    assert harness.should_unlock(90) is True
    assert harness.UNLOCK_PERCENT == 90


def test_opening_ends_with_mentor_and_leads_with_talent():
    order = harness.opening_order("学者")
    assert order[0] == "jiahui"
    assert order[-1] == "shanyu"
    assert len(order) == 4


def test_reply_cast_prefers_talent_and_mentor_every_third_turn():
    cast = harness.pick_reply_cast("今晚站桩怎么打卡", "行者", None, 3)
    assert cast[0] == "limo"
    assert "shanyu" in cast
    assert len(cast) <= 2


def test_at_wakes_that_character_and_quote_wakes_the_author():
    from app.agents.academy.graph import plan_cast
    from app.agents.academy.talk import build_user_line, clean_sticker, resolve_mention

    directed = plan_cast({
        "mode": "reply",
        "mention": "limo",
        "user_turns": 3,
        "last_who": "dani",
    })
    assert directed["speakers"] == ["limo"]

    quoted = plan_cast({
        "mode": "reply",
        "quote": {"who": "jiahui", "text": "按标准来"},
        "user_turns": 1,
    })
    assert quoted["speakers"] == ["jiahui"]

    assert resolve_mention("@王家慧 我站不住", None) == "jiahui"
    assert clean_sticker("😂") == "😂"
    assert clean_sticker("<img src=x>") is None
    row = build_user_line("我站不住", "limo", {"who": "jiahui", "text": "按标准来"}, "😂")
    assert row["mention"] == "limo"
    assert row["text"].startswith("@李寞")
    assert row["quote"]["who"] == "jiahui"
    assert row["sticker"] == "😂"


def test_speak_keeps_the_model_line(monkeypatch):
    async def _line(**kwargs):
        assert kwargs["disable_thinking"] is True
        return "今晚我跟你一组，你站左边我看着。"

    monkeypatch.setattr(harness, "chat_completion", _line)
    line = asyncio.run(harness.speak(
        "limo",
        episode_title="E13 五兽桩",
        task="站桩5分钟",
        child_talent="行者",
        prior=[{"who": "me", "text": "今晚站桩谁跟我一组"}],
        instruction="直接回答",
    ))
    assert line["text"] == "今晚我跟你一组，你站左边我看着。"
    assert line["text"] not in harness.CHARACTERS["limo"].samples


def test_speak_falls_back_when_llm_empty(monkeypatch):
    async def _empty(**kwargs):
        return None

    monkeypatch.setattr(harness, "chat_completion", _empty)
    line = asyncio.run(harness.speak(
        "limo",
        episode_title="E13 五兽桩",
        task="站桩5分钟",
        child_talent="行者",
        prior=[],
        instruction="说一句",
    ))
    assert line["who"] == "limo"
    assert line["text"]


def test_catalog_has_current_episode():
    from app.agents.academy.catalog import CURRENT_EPISODE_ID, get_episode

    ep = get_episode("e13")
    assert ep is not None
    assert ep.id == CURRENT_EPISODE_ID
    assert ep.task == "站桩5分钟"


def test_e13_perception_stops_before_later_acts():
    from app.agents.academy.perception import leaks_future, time_box

    box = time_box("yuchen", "E13", "E13 五兽桩")
    assert "第三幕" in box
    assert "第五幕" in box
    assert "不许提" in box
    assert "画中人" in box
    assert leaks_future("我们去闯五关吧", "E13") is True
    assert leaks_future("腿还没看懂", "E13") is False


def test_graph_opening_runs_in_order(monkeypatch):
    from app.agents.academy.graph import build_scene_graph

    async def _line(**kwargs):
        return "腿还没看懂"

    monkeypatch.setattr(harness, "chat_completion", _line)

    async def _run():
        graph = build_scene_graph()
        return await graph.ainvoke({
            "mode": "opening",
            "episode_id": "E13",
            "episode_title": "E13 五兽桩",
            "task": "站桩5分钟",
            "child_talent": "学者",
            "prior": [],
            "turns": [],
        })

    result = asyncio.run(_run())
    whos = [turn["who"] for turn in result["turns"]]
    assert whos[0] == "jiahui"
    assert whos[-1] == "shanyu"
    assert all(turn["text"] for turn in result["turns"])


def test_demo_fills_missing_watch_and_media():
    from app.services.academy.demo import DEMO_MEDIA_IDS, DEMO_WATCHED_IDS, media_kind
    from app.services.academy.sector import episode_status

    assert "E12" in DEMO_WATCHED_IDS
    assert "E13" not in DEMO_WATCHED_IDS
    assert media_kind("E13", "") == "demo"
    assert media_kind("E14", "") == "none"
    assert media_kind("E13", "xueyuan/E13.mp4") == "oss"
    assert episode_status(unlocked=True, media="demo", prev_ready=True, act_locked=False) == "watched"
    assert episode_status(unlocked=False, media="demo", prev_ready=True, act_locked=False) == "open"
    assert episode_status(unlocked=False, media="none", prev_ready=True, act_locked=False) == "upcoming"
