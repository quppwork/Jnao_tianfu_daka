"""每个画中人是独立子图：私有会话在 Checkpointer，配置感知在 Store。"""

import asyncio

from app.agents.academy import harness


def test_bot_keeps_its_own_lines(monkeypatch):
    from app.agents.academy.graph import bot_graph
    from app.agents.academy.runtime import thread_id

    async def _line(**kwargs):
        return "腿还没看懂"

    monkeypatch.setattr(harness, "chat_completion", _line)
    graph = bot_graph("limo")
    config = {"configurable": {"thread_id": thread_id(71, "E13", "limo")}}
    payload = {
        "character_key": "limo",
        "episode_id": "E13",
        "episode_title": "E13 五兽桩",
        "task": "站桩5分钟",
        "child_talent": "行者",
        "child_user_id": 71,
        "instruction": "说一句",
        "channel": [],
    }

    async def _run():
        first = await graph.ainvoke(payload, config)
        second = await graph.ainvoke(payload, config)
        return first, second

    first, second = asyncio.run(_run())
    assert first["line"]["bot_id"] == "bot_limo"
    assert len(first["private"]) == 1
    assert len(second["private"]) == 2
    assert second["private"][0]["text"] == first["line"]["text"]


def test_canon_update_is_visible_to_that_bot_only(monkeypatch):
    from app.agents.academy.graph import bot_graph
    from app.agents.academy.runtime import put_canon, thread_id

    seen = []

    async def _line(**kwargs):
        seen.append(kwargs.get("system_prompt") or "")
        return "先站五分钟"

    monkeypatch.setattr(harness, "chat_completion", _line)
    put_canon("bot_jiahui", "constraint", "不许提第五幕", None, 9)
    graph = bot_graph("jiahui")

    async def _run():
        await graph.ainvoke(
            {
                "character_key": "jiahui",
                "episode_id": "E13",
                "episode_title": "E13 五兽桩",
                "task": "站桩5分钟",
                "child_talent": "学者",
                "child_user_id": 72,
                "instruction": "说一句",
                "channel": [{"who": "me", "text": "谁在说话"}],
            },
            {"configurable": {"thread_id": thread_id(72, "E13", "jiahui")}},
        )
        await bot_graph("dani").ainvoke(
            {
                "character_key": "dani",
                "episode_id": "E13",
                "episode_title": "E13 五兽桩",
                "task": "站桩5分钟",
                "child_talent": "德者",
                "child_user_id": 72,
                "instruction": "说一句",
                "channel": [],
            },
            {"configurable": {"thread_id": thread_id(72, "E13", "dani")}},
        )

    asyncio.run(_run())
    assert any("不许提第五幕" in item and "bot_jiahui" in item for item in seen)
    assert seen[-1]
    assert "不许提第五幕" not in seen[-1]
    assert "用户没有编号" in seen[0]


def test_reopen_keeps_the_user_line(db_session):
    import asyncio

    from app.db.models import AcademyProgress, AcademyRoom
    from app.services.academy.room import open_room

    db_session.add(AcademyProgress(
        child_user_id=7, episode_id="E13", percent=100, unlocked=1,
    ))
    db_session.add(AcademyRoom(
        child_user_id=7,
        episode_id="E13",
        messages=[
            {"who": "jiahui", "text": "按标准来"},
            {"who": "me", "text": "我站不住"},
        ],
        user_turns=1,
    ))
    db_session.commit()

    result = asyncio.run(open_room(db_session, 7, "E13"))
    assert result["replay"] is True
    assert [row["who"] for row in result["turns"]] == ["jiahui", "me"]
    assert result["turns"][1]["text"] == "我站不住"


def test_chat_saves_the_user_line_before_the_model(db_session, monkeypatch):
    from sqlalchemy import select

    from app.db.models import AcademyProgress, AcademyRoom
    from app.services.academy.room import chat

    seen = {}

    async def _boom(*_args, **kwargs):
        seen["prior"] = list(kwargs.get("prior") or [])
        raise RuntimeError("model down")

    monkeypatch.setattr("app.services.academy.room.reply_turns", _boom)
    db_session.add(AcademyProgress(
        child_user_id=7, episode_id="E13", percent=100, unlocked=1,
    ))
    db_session.commit()

    result = asyncio.run(chat(db_session, 7, "E13", "我站不住"))
    assert result["turns"]
    assert all(row["who"] != "me" for row in result["turns"])

    db_session.expire_all()
    room = db_session.scalar(
        select(AcademyRoom).where(
            AcademyRoom.child_user_id == 7,
            AcademyRoom.episode_id == "E13",
        )
    )
    assert room is not None
    assert room.user_turns == 1
    assert any(m.get("who") == "me" and m.get("text") == "我站不住" for m in room.messages)
    assert seen["prior"] == []
