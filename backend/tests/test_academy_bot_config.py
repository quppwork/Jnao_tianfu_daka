"""角色配置合同：一个 Bot 的提示词、约束、剧本、剧情可上传，记忆按 Bot 分开。"""

from app.agents.academy.characters import bot_id_for
from app.services.academy.bots import (
    ensure_bots,
    list_bots,
    perceive_session,
    update_persona,
    upload_script,
    wake_bot,
)


def test_every_character_reuses_same_bot_shape(db_session):
    bots = list_bots(db_session)
    assert {row.bot_id for row in bots} >= {"bot_yuchen", "bot_dani", "bot_shanyu"}
    yuchen = next(row for row in bots if row.bot_id == "bot_yuchen")
    dani = next(row for row in bots if row.bot_id == "bot_dani")
    assert yuchen.character_key == "yuchen"
    assert yuchen.persona_prompt and dani.persona_prompt
    assert yuchen.persona_prompt != dani.persona_prompt
    assert bot_id_for("limo") == "bot_limo"


def test_persona_and_constraint_update_write_own_memory(db_session):
    ensure_bots(db_session)
    updated = update_persona(
        db_session,
        "bot_yuchen",
        persona_prompt="我是章宇尘。先把道理想明白，再承认腿还没跟上。",
        constraints="只谈已经播到的这一集。不许剧透第五幕。",
    )
    assert updated.revision == 2
    kinds = [row.kind for row in updated.memories]
    assert kinds == ["persona", "constraint"]
    assert all(row.bot_id == "bot_yuchen" for row in updated.memories)
    assert "第五幕" in updated.memories[1].content


def test_script_and_plot_upload_is_per_bot(db_session):
    ensure_bots(db_session)
    yuchen = upload_script(
        db_session,
        "bot_yuchen",
        "E13",
        script_body="宇尘躺在床上把十桩功在脑子里走了一遍。",
        plot_summary="五兽桩这一集，他懂了原理，身体还没跟上。",
    )
    dani = upload_script(
        db_session,
        "bot_dani",
        "E13",
        script_body="丹尼盯着师父的收势，小声问能不能吃东西。",
        plot_summary="同一集里，丹尼在意的是约定和吃的。",
    )
    assert yuchen.script.revision == 1
    assert dani.script.script_body != yuchen.script.script_body
    assert {row.kind for row in yuchen.memories} == {"script", "plot"}
    assert all(row.bot_id == "bot_yuchen" for row in yuchen.memories)


def test_session_marks_user_and_peer_bots():
    seen = perceive_session("bot_yuchen", [
        {"who": "me", "text": "我站不住"},
        {"who": "limo", "text": "我陪你站"},
        {"who": "yuchen", "text": "腿还没看懂"},
    ])
    assert seen[0]["role"] == "user"
    assert seen[0]["bot_id"] is None
    assert seen[1]["role"] == "bot"
    assert seen[1]["bot_id"] == "bot_limo"
    assert seen[1]["peer"] is True
    assert seen[2]["bot_id"] == "bot_yuchen"
    assert seen[2]["peer"] is False


def test_session_memory_is_stored_per_bot(db_session):
    from app.services.academy.bots import remember_session

    ensure_bots(db_session)
    row = remember_session(
        db_session,
        "bot_yuchen",
        child_user_id=7,
        episode_id="E13",
        lines=[{"who": "me", "text": "谁在说话"}, {"who": "dani", "text": "拉钩"}],
    )
    assert row.bot_id == "bot_yuchen"
    assert row.messages[0]["role"] == "user"
    assert row.messages[1]["bot_id"] == "bot_dani"
    assert row.messages[1]["peer"] is True
    import random

    rng = random.Random(2)
    picked = [wake_bot(["bot_yuchen", "bot_dani", "bot_limo"], "bot_yuchen", rng) for _ in range(12)]
    assert "bot_yuchen" not in picked
    assert len(set(picked)) >= 1
    assert set(picked) <= {"bot_dani", "bot_limo"}


def test_config_api_reused_across_bots(client, registered_user):
    uid = registered_user["child_user_id"]
    listed = client.get(f"/api/academy/bots?user_id={uid}")
    assert listed.status_code == 200
    ids = [item["bot_id"] for item in listed.json()["bots"]]
    assert "bot_yuchen" in ids and "bot_chenxue" in ids

    saved = client.put(
        f"/api/academy/bots/bot_yuchen?user_id={uid}",
        json={
            "persona_prompt": "章宇尘：想明白再动。",
            "constraints": "画中人，不剧透。",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["bot_id"] == "bot_yuchen"
    assert body["revision"] == 2
    assert body["memories"][0]["kind"] == "persona"

    other = client.post(
        f"/api/academy/bots/bot_chenxue/episodes/E13/script?user_id={uid}",
        json={"script_body": "陈雪想比一场。", "plot_summary": "她把这一集看成挑战。"},
    )
    assert other.status_code == 200
    assert other.json()["bot_id"] == "bot_chenxue"
    assert other.json()["episode_id"] == "E13"
