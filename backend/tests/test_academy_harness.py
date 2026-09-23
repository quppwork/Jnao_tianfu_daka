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


def test_reply_wakes_two_at_random_and_pins_mention():
    cast = harness.wake_speakers(
        mention=None, quote_who=None, last_who="dani", episode_id="E13"
    )
    assert len(cast) == 2
    assert len(set(cast)) == 2
    assert "dani" not in cast or cast[0] != "dani"


def test_at_wakes_that_character_and_quote_wakes_the_author():
    from app.agents.academy.graph import plan_cast
    from app.agents.academy.talk import build_user_line, clean_sticker, resolve_mention

    directed = plan_cast({
        "mode": "reply",
        "episode_id": "E13",
        "mention": "limo",
        "user_turns": 3,
        "last_who": "dani",
    })
    assert directed["speakers"][0] == "limo"
    assert len(directed["speakers"]) == 2
    assert directed["speakers"][1] != "limo"

    quoted = plan_cast({
        "mode": "reply",
        "episode_id": "E13",
        "quote": {"who": "jiahui", "text": "按标准来"},
        "user_turns": 1,
    })
    assert quoted["speakers"][0] == "jiahui"
    assert len(quoted["speakers"]) == 2

    plot_q = plan_cast({
        "mode": "reply",
        "episode_id": "E13",
        "user_text": "戴上眼罩你怕不怕黑？",
        "user_turns": 1,
    })
    assert len(plot_q["speakers"]) == 2
    assert len(set(plot_q["speakers"])) == 2

    assert resolve_mention("@王家慧 我站不住", None) == "jiahui"
    assert clean_sticker("😂") == "😂"
    assert clean_sticker("<img src=x>") is None
    row = build_user_line("我站不住", "limo", {"who": "jiahui", "text": "按标准来"}, "😂")
    assert row["mention"] == "limo"
    assert row["text"].startswith("@李寞")
    assert row["quote"]["who"] == "jiahui"
    assert row["sticker"] == "😂"
    only = build_user_line("", None, None, "🥺")
    assert only["sticker"] == "🥺"
    assert only["text"] == "🥺"
    from app.agents.academy.talk import annotate_for_model
    assert "可怜" in annotate_for_model(only) or "表情" in annotate_for_model(only)
    # 小表情只发正文：不抬成大贴纸字段，但仍能给模型注口语提示
    solo = build_user_line("😅", None, None, None)
    assert "sticker" not in solo
    assert solo["text"] == "😅"
    assert "表情" in annotate_for_model(solo) or "尴尬" in annotate_for_model(solo)


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
    assert harness.looks_echo("你好呀", "你好") is False
    assert harness.misses_ask("嗨，在呢", "你好") is False
    assert harness._clean_line("你好呀", avoid=[], user_ask="你好") == "你好呀"
    assert harness.prior_said([{"who": "me", "text": "你好"}, {"who": "dani", "text": "嗨"}]) == ["嗨"]


def test_speak_keeps_the_model_line(monkeypatch):
    async def _line(**kwargs):
        msg = kwargs.get("user_message") or ""
        if "不要写 Say" in msg or "思考步" in msg:
            return "Thought: 孩子问谁跟他一组\nAction: answer\nObservation: 直接答应"
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


def test_parse_react_say_and_alike():
    assert harness.parse_react_say(
        "Thought: a\nAction: answer\nObservation: b\nSay: 别怕，黑只是关灯。"
    ) == "别怕，黑只是关灯。"
    assert harness.alike("别怕黑。黑只是把眼睛关了。", "别怕黑。黑只是把眼睛关了。")
    assert harness.alike("别怕黑黑只是把眼睛关了", "别怕黑。黑只是把眼睛关了。")
    assert not harness.alike("五个世界我最想问老师", "别怕黑。黑只是把眼睛关了。")
    # 同题再答：不再因与旧句相似而丢弃
    old = "种姓靠血统锁人，科举把锁撬开了，所以咱们没走那条路。"
    new = "没有。印度种姓靠血统卡位，咱们这边有科举，普通人也能往上考，所以没搞那一套。"
    assert harness._clean_line(new, avoid=[old], user_ask="@王家慧 中国有种姓制度么") == new[:80]
    assert harness._clean_line(old, avoid=[old], user_ask="中国为什么没有种姓？") == old[:80]
    scratch = harness.parse_react_scratch(
        "Thought: 问感觉\nAction: example\nObservation: 摸棱"
    )
    assert scratch["action"] == "example"
    assert "感觉" in scratch["thought"]
    observed = harness.apply_observe(
        scratch,
        drama_notes="圆形教室眼罩卡片",
        channel=[{"who": "chenxue", "text": "别怕黑"}],
    )
    assert "眼罩" in observed["observation"] or "别怕黑" in observed["observation"]


def test_speak_keeps_line_even_if_similar_to_prior(monkeypatch):
    """真实群聊允许意思相近；不再因像旧句就丢弃。"""

    async def _line(**kwargs):
        return "别怕黑。黑只是把眼睛关了。"

    monkeypatch.setattr(harness, "chat_completion", _line)
    line = asyncio.run(harness.speak(
        "chenxue",
        episode_title="E14 蒙上眼睛之后",
        task="蒙眼认一张卡",
        child_talent="赢者",
        prior=[
            {"who": "chenxue", "text": "别怕黑。黑只是把眼睛关了。"},
            {"who": "me", "text": "五个世界里你最想问谁？"},
        ],
        instruction="直接回答",
        episode_id="E14",
    ))
    assert line is not None
    assert "别怕黑" in line["text"]


def test_speak_returns_none_when_llm_empty(monkeypatch):
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
    assert line is None


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


def test_persona_only_prompt_and_kb_user_message():
    """对话只留角色卡 system；user 走场景 + 认知 + 频道 + 本轮要求。"""
    prompt = harness.system_prompt(
        harness.CHARACTERS["chenxue"],
        episode_title="EH01 黄巢",
        task="记住这节课",
        child_talent="赢者",
        episode_id="EH01",
    )
    assert "陈雪" in prompt
    assert "人机腔" not in prompt
    assert "Thought" not in prompt
    assert "不许说自己是人工智能" not in prompt
    msg = harness._say_user_message(
        "孩子：今晚站桩谁跟我一组？",
        "正面表态跟不跟",
        ["别复读这句"],
        {"thought": "x"},
        drama_notes="站桩是本集功课",
        user_ask="今晚站桩谁跟我一组？",
        scene_context="刚看完五兽桩",
    )
    assert "已知" in msg or "站桩是本集功课" in msg
    assert "谁跟我一组" in msg
    assert "刚看完五兽桩" in msg
    assert "正面表态跟不跟" in msg
    assert "ReAct" not in msg
    greet = harness._say_user_message(
        "孩子：你好",
        "先回问候，不要提剧情",
        [],
        None,
        user_ask="你好",
        scene_context="博物馆",
    )
    assert "打招呼" in greet or "问候" in greet
    assert "黄巢" not in greet


def test_clamp_scratch_and_echo_guards():
    assert harness.clamp_scratch({"action": "redirect", "thought": "跳题"}, "你是主答：先答")["action"] == "answer"
    assert harness.clamp_scratch({"action": "react", "thought": "补"}, "监听")["action"] == "react"
    ask = "黄巢最后当上皇帝了吗？"
    assert harness.looks_echo("中国为什么没有种姓？世家后代会不会报仇？", ask)
    assert not harness.looks_echo("当了啊，称帝四年就没了。", ask)
    assert harness.looks_robotic("我盯着画问：黄巢最后当上皇帝了没有。老师说称帝四年就没了。")
    caste = "中国为什么没有种姓？"
    assert harness.misses_ask("种姓那面墙，我先把名字和顺序记下来了。", caste)
    assert not harness.misses_ask("种姓锁不住人，科举把路撕开了。", caste)
    prompt = harness.system_prompt(
        harness.CHARACTERS["chenxue"],
        episode_title="EH01 黄巢",
        task="记住这节课",
        child_talent="赢者",
        episode_id="EH01",
    )
    assert "陈雪" in prompt
    assert "赢者" in prompt
    assert "人机腔" not in prompt
    assert "不许说自己是人工智能" not in prompt


def test_say_line_returns_none_when_llm_empty(monkeypatch):
    from app.agents.academy.packs import clear_pack_cache

    clear_pack_cache()

    async def _empty(**kwargs):
        return None

    monkeypatch.setattr(harness, "chat_completion", _empty)
    line = asyncio.run(harness.say_line(
        "jiahui",
        episode_title="EH01 历史课·黄巢篇",
        task="记住今天这节历史课",
        child_talent="学者",
        prior=[{"who": "me", "text": "中国为什么没有种姓？"}],
        instruction="你是主答：先正面答",
        scratch={"thought": "答种姓", "action": "answer", "observation": ""},
        episode_id="EH01",
    ))
    assert line is None


def test_eh01_pack_fact_seed_matches_ask():
    from app.agents.academy.packs import clear_pack_cache, pack_fact_seed, pack_synopsis
    from app.agents.academy.turn import prepare_turn, turn_instruction

    clear_pack_cache()
    text = pack_fact_seed("EH01", "中国为什么没有种姓？", "chenxue")
    assert "科举" in text
    assert "种姓" in text or "锁" in text
    emperor = pack_fact_seed("EH01", "黄巢最后当上皇帝了吗？", "yuchen")
    assert "当" in emperor or "称" in emperor or "四年" in emperor
    assert pack_fact_seed("EH01", "你们能帮我总结一下剧情么", "yuchen") == ""
    assert "黄巢" in pack_synopsis("EH01") or "博物馆" in pack_synopsis("EH01")
    ctx = prepare_turn(
        user_text="你们能帮我总结一下剧情么",
        episode_id="EH01",
        character_keys=["yuchen", "chenxue"],
    )
    assert ctx.skill == "summary"
    assert ctx.reasoning_mode == "react"
    hint = turn_instruction(ctx, character_key="yuchen", index=0)
    assert "总结" in hint
    hist = prepare_turn(
        user_text="中国为什么没有种姓？",
        episode_id="EH01",
        character_keys=["chenxue", "dani"],
    )
    assert hist.skill == "answer"
    assert hist.fact_for("chenxue")
    assert "科举" in hist.fact_for("chenxue") or "锁" in hist.fact_for("chenxue")


def test_caste_no_fake_line_when_llm_empty(monkeypatch):
    from app.agents.academy.packs import clear_pack_cache

    clear_pack_cache()

    async def _empty(**kwargs):
        return None

    monkeypatch.setattr(harness, "chat_completion", _empty)
    line = asyncio.run(harness.say_line(
        "chenxue",
        episode_title="EH01 历史课·黄巢篇",
        task="记住今天这节历史课",
        child_talent="赢者",
        prior=[{"who": "me", "text": "中国为什么没有种姓？"}],
        instruction="先答孩子",
        scratch={"thought": "答种姓", "action": "answer", "observation": "科举"},
        episode_id="EH01",
    ))
    assert line is None


def test_graph_opening_runs_in_order(monkeypatch):
    from app.agents.academy.graph import build_scene_graph

    async def _line(**kwargs):
        system = kwargs.get("system_prompt") or ""
        # 按「你是某某」匹配，避免关系字段里的导师名误伤
        for prefix, text in (
            ("你是善雨", "先定心。"),
            ("你是王家慧", "笔记写好了。"),
            ("你是章宇尘", "原理我懂了。"),
            ("你是施丹尼", "你站我就站。"),
            ("你是李寞", "站一分钟算一分钟。"),
            ("你是陈雪", "再来一次。"),
        ):
            if prefix in system:
                return text
        return "在。"

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


def test_invite_uses_model_not_canned_fallback(monkeypatch):
    """组队意图走模型；空响应不返回假台词。"""
    ask = "今晚站桩谁跟我一组？"

    async def _line(**kwargs):
        return "算我一个，跟你一组。"

    monkeypatch.setattr(harness, "chat_completion", _line)
    first = asyncio.run(harness.say_line(
        "chenxue",
        episode_title="E13 五兽桩",
        task="站桩5分钟",
        child_talent="赢者",
        prior=[{"who": "me", "text": ask}],
        instruction="感知：找人组队",
        scratch={"thought": "应邀", "action": "react", "observation": ""},
        episode_id="E13",
    ))
    assert first is not None
    assert first["text"] == "算我一个，跟你一组。"
    assert first["text"] != "嗯，我听着。"

    async def _empty(**kwargs):
        return None

    monkeypatch.setattr(harness, "chat_completion", _empty)
    empty = asyncio.run(harness.say_line(
        "limo",
        episode_title="E13 五兽桩",
        task="站桩5分钟",
        child_talent="行者",
        prior=[{"who": "me", "text": ask}],
        instruction="感知：找人组队",
        scratch={"thought": "也算我", "action": "react", "observation": ""},
        episode_id="E13",
    ))
    assert empty is None

    from app.agents.academy.turn import is_invite, prepare_turn, turn_instruction

    assert is_invite(ask)
    ctx = prepare_turn(user_text=ask, episode_id="E13", character_keys=["chenxue", "limo"])
    assert ctx.skill == "train"
    hint = turn_instruction(ctx, character_key="chenxue", index=0)
    assert "组队" in hint or "应邀" in hint or "跟不跟" in hint


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
