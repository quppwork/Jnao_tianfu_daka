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
    assert directed["speakers"][0] == "limo"
    assert len(directed["speakers"]) == 2
    assert directed["speakers"][1] != "limo"

    quoted = plan_cast({
        "mode": "reply",
        "quote": {"who": "jiahui", "text": "按标准来"},
        "user_turns": 1,
    })
    assert quoted["speakers"][0] == "jiahui"
    assert len(quoted["speakers"]) == 2

    assert resolve_mention("@王家慧 我站不住", None) == "jiahui"
    assert clean_sticker("😂") == "😂"
    assert clean_sticker("<img src=x>") is None
    row = build_user_line("我站不住", "limo", {"who": "jiahui", "text": "按标准来"}, "😂")
    assert row["mention"] == "limo"
    assert row["text"].startswith("@李寞")
    assert row["quote"]["who"] == "jiahui"
    assert row["sticker"] == "😂"


def test_mood_sinks_when_the_child_is_down_and_then_fades():
    from app.agents.academy.affect import rank_speakers, step

    first = step(None, "好累不想站了")
    assert first["valence"] < 0
    second = step(first, "还是好累不想动")
    assert second["valence"] < first["valence"]
    eased = step(second, "嗯")
    assert eased["valence"] > second["valence"]
    named = rank_speakers(
        mention="limo",
        quote_who=None,
        last_who="chenxue",
        text="哈喽",
        affect=eased,
    )
    assert named[0] == "limo"
    assert named[1] != "limo"
    assert harness.route_topic("这道数学题怎么做") == "qa"
    assert harness.route_topic("这集师父为什么收势") == "plot"
    assert harness.read_mood("今晚好累不想站了") == "low"
    assert harness.is_greeting("你好") is True
    assert harness.is_greeting("师父，十桩功最难的是哪一桩") is False


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


def test_e14_and_huangchao_senses_are_independent():
    from app.agents.academy.catalog import SWITCHABLE_IDS, get_episode
    from app.agents.academy.perception import leaks_future, time_box

    assert SWITCHABLE_IDS == ("E13", "E14", "EH01")
    assert get_episode("E14").oss_key == "AIshipin/E14_blindfold_720p.mp4"
    assert get_episode("EH01").oss_key == "AIshipin/EH01_huangchao_720p.mp4"
    from app.services.academy.demo import media_kind
    assert media_kind("E14", get_episode("E14").oss_key) == "oss"
    assert media_kind("EH01", get_episode("EH01").oss_key) == "oss"
    e14 = time_box("jiahui", "E14", "蒙上眼睛之后")
    assert "黑三角" in e14 or "红" in e14
    assert "站桩" not in e14
    hx = time_box("chenxue", "EH01", "历史课·黄巢篇")
    assert "种姓" in hx or "黄巢" in hx or "博物馆" in hx
    assert leaks_future("我们去闯五角迷宫", "EH01") is True
    assert leaks_future("那首诗我抄了", "EH01") is False


def test_e13_perception_stops_before_later_acts():
    from app.agents.academy.perception import leaks_future, time_box

    box = time_box("yuchen", "E13", "E13 五兽桩")
    assert "第三幕" in box
    assert "第五幕" in box
    assert "不许提" in box
    assert "画中人" in box
    assert leaks_future("我们去闯五关吧", "E13") is True
    assert leaks_future("腿还没看懂", "E13") is False


def test_greeting_hint_does_not_open_a_stance_topic():
    from app.agents.academy.graph import _hint

    hint = _hint({
        "mode": "reply",
        "user_text": "你好",
        "index": 1,
        "speakers": ["yuchen", "chenxue"],
    }, "chenxue")
    assert "先回" in hint
    assert "小话题" not in hint
    assert "站桩" in hint


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
    assert "E14" not in DEMO_WATCHED_IDS
    assert "EH01" not in DEMO_WATCHED_IDS
    assert media_kind("E13", "") == "demo"
    assert media_kind("E14", "") == "demo"
    assert media_kind("EH01", "") == "demo"
    assert media_kind("E14", "AIshipin/E14_blindfold_720p.mp4") == "oss"
    assert media_kind("EH01", "AIshipin/EH01_huangchao_720p.mp4") == "oss"
    assert media_kind("E15", "") == "none"
    assert media_kind("E13", "xueyuan/E13.mp4") == "oss"
    assert episode_status(unlocked=True, media="demo", prev_ready=True, act_locked=False) == "watched"
    assert episode_status(unlocked=False, media="demo", prev_ready=True, act_locked=False) == "open"
    assert episode_status(unlocked=False, media="none", prev_ready=True, act_locked=False) == "upcoming"
