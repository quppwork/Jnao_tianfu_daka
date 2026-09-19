"""画中人配置与记忆。六个角色同一套函数，不按人写分支。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.academy.characters import CHARACTERS, bot_id_for
from app.db.models import AcademyBot, AcademyBotMemory, AcademyBotScript, AcademyBotSession
from app.services.academy.errors import AcademyError

_KIND_LABEL = {
    "persona": "人物提示词",
    "constraint": "约束",
    "script": "剧本",
    "plot": "剧情",
}


@dataclass
class BotChange:
    bot: AcademyBot
    memories: list[AcademyBotMemory]
    script: AcademyBotScript | None = None

    @property
    def revision(self) -> int:
        return int(self.bot.revision or 1)

    @property
    def bot_id(self) -> str:
        return self.bot.bot_id


def default_persona(key: str) -> str:
    char = CHARACTERS[key]
    samples = " / ".join(char.samples)
    return f"{char.name}（{char.tag}）。说话：{char.voice} 口吻参考：{samples}"


def default_constraints(key: str) -> str:
    char = CHARACTERS[key]
    return f"{char.steer}。只说这一集已经发生的事。不许说自己是人工智能。"


def ensure_bots(db: Session) -> None:
    existing = {row.character_key for row in db.scalars(select(AcademyBot)).all()}
    for key, char in CHARACTERS.items():
        if key in existing:
            continue
        db.add(AcademyBot(
            bot_id=bot_id_for(key),
            character_key=key,
            name=char.name,
            tag=char.tag,
            persona_prompt=default_persona(key),
            constraints=default_constraints(key),
            voice=char.voice,
            steer=char.steer,
            revision=1,
        ))
    db.commit()


def list_bots(db: Session) -> list[AcademyBot]:
    ensure_bots(db)
    return list(db.scalars(select(AcademyBot).order_by(AcademyBot.bot_id)).all())


def get_bot(db: Session, bot_id: str) -> AcademyBot:
    ensure_bots(db)
    row = db.get(AcademyBot, bot_id)
    if row is None:
        raise AcademyError("没有这个角色", 404)
    return row


def _snippet(text: str) -> str:
    return " ".join((text or "").split())[:120]


def _remember(
    db: Session,
    bot: AcademyBot,
    kind: str,
    body: str,
    *,
    episode_id: str | None,
) -> AcademyBotMemory:
    row = AcademyBotMemory(
        bot_id=bot.bot_id,
        episode_id=episode_id,
        kind=kind,
        content=f"我感知到{_KIND_LABEL[kind]}更新：{_snippet(body)}",
        revision=int(bot.revision or 1),
    )
    db.add(row)
    return row


def update_persona(
    db: Session,
    bot_id: str,
    *,
    persona_prompt: str | None = None,
    constraints: str | None = None,
) -> BotChange:
    bot = get_bot(db, bot_id)
    memories: list[AcademyBotMemory] = []
    changed = False
    if persona_prompt is not None and persona_prompt.strip() and persona_prompt != bot.persona_prompt:
        bot.persona_prompt = persona_prompt.strip()
        changed = True
        memories.append(_remember(db, bot, "persona", bot.persona_prompt, episode_id=None))
    if constraints is not None and constraints.strip() and constraints != bot.constraints:
        bot.constraints = constraints.strip()
        changed = True
        memories.append(_remember(db, bot, "constraint", bot.constraints, episode_id=None))
    if changed:
        bot.revision = int(bot.revision or 1) + 1
        for row in memories:
            row.revision = bot.revision
    db.commit()
    for row in memories:
        db.refresh(row)
    db.refresh(bot)
    from app.agents.academy.runtime import put_canon

    for row in memories:
        put_canon(bot.bot_id, row.kind, row.content, row.episode_id, row.revision)
    return BotChange(bot=bot, memories=memories)


def upload_script(
    db: Session,
    bot_id: str,
    episode_id: str,
    *,
    script_body: str,
    plot_summary: str,
) -> BotChange:
    bot = get_bot(db, bot_id)
    episode_id = episode_id.strip().upper()
    script = db.scalar(
        select(AcademyBotScript).where(
            AcademyBotScript.bot_id == bot.bot_id,
            AcademyBotScript.episode_id == episode_id,
        )
    )
    if script is None:
        script = AcademyBotScript(bot_id=bot.bot_id, episode_id=episode_id, revision=0)
        db.add(script)
    script.script_body = (script_body or "").strip()
    script.plot_summary = (plot_summary or "").strip()
    script.revision = int(script.revision or 0) + 1
    bot.revision = int(bot.revision or 1) + 1
    memories = []
    if script.script_body:
        memories.append(_remember(db, bot, "script", script.script_body, episode_id=episode_id))
    if script.plot_summary:
        memories.append(_remember(db, bot, "plot", script.plot_summary, episode_id=episode_id))
    for row in memories:
        row.revision = bot.revision
    db.commit()
    db.refresh(bot)
    db.refresh(script)
    from app.agents.academy.runtime import put_canon

    for row in memories:
        put_canon(bot.bot_id, row.kind, row.content, row.episode_id, row.revision)
    return BotChange(bot=bot, memories=memories, script=script)


def perceive_session(self_bot_id: str, lines: list[dict]) -> list[dict]:
    """把讨论区原文标成：用户，还是哪一个画中人。"""
    out = []
    for line in lines:
        who = str(line.get("who") or "")
        text = str(line.get("text") or "")
        if who in ("me", "user", ""):
            out.append({
                "role": "user",
                "bot_id": None,
                "name": "用户",
                "text": text,
                "peer": False,
            })
            continue
        peer_id = bot_id_for(who)
        char = CHARACTERS.get(who)
        out.append({
            "role": "bot",
            "bot_id": peer_id,
            "name": char.name if char else who,
            "text": text,
            "peer": peer_id != self_bot_id,
        })
    return out


def remember_session(
    db: Session,
    bot_id: str,
    *,
    child_user_id: int,
    episode_id: str,
    lines: list[dict],
) -> AcademyBotSession:
    bot = get_bot(db, bot_id)
    episode_id = episode_id.strip().upper()
    row = db.scalar(
        select(AcademyBotSession).where(
            AcademyBotSession.bot_id == bot.bot_id,
            AcademyBotSession.child_user_id == child_user_id,
            AcademyBotSession.episode_id == episode_id,
        )
    )
    if row is None:
        row = AcademyBotSession(
            bot_id=bot.bot_id,
            child_user_id=child_user_id,
            episode_id=episode_id,
            messages=[],
        )
        db.add(row)
    viewed = perceive_session(bot.bot_id, lines)
    row.messages = (list(row.messages or []) + viewed)[-40:]
    db.commit()
    db.refresh(row)
    return row


def wake_bot(bot_ids: list[str], last_bot_id: str | None, rng: random.Random | None = None) -> str:
    """随机唤醒另一个画中人。场上只剩自己时才再次开口。"""
    pool = [item for item in bot_ids if item != last_bot_id] or list(bot_ids)
    if not pool:
        raise AcademyError("没有可唤醒的角色")
    return (rng or random.Random()).choice(pool)


def identity_box(self_key: str) -> str:
    self_id = bot_id_for(self_key)
    peers = [
        f"{char.name}（{bot_id_for(key)}）"
        for key, char in CHARACTERS.items()
        if key != self_key
    ]
    return (
        f"你的编号是 {self_id}。用户没有编号。\n"
        f"其他画中人：{'、'.join(peers)}。你们可以互相接话，不要把自己说成用户。"
    )


def bot_payload(bot: AcademyBot, memories: list[AcademyBotMemory] | None = None) -> dict:
    return {
        "bot_id": bot.bot_id,
        "character_key": bot.character_key,
        "name": bot.name,
        "tag": bot.tag,
        "persona_prompt": bot.persona_prompt,
        "constraints": bot.constraints,
        "revision": int(bot.revision or 1),
        "memories": [
            {
                "kind": row.kind,
                "episode_id": row.episode_id,
                "content": row.content,
                "revision": row.revision,
            }
            for row in (memories or [])
        ],
    }
