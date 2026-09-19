"""讨论区。只负责落库和调用 harness，不组装三页目录。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.academy.catalog import Episode, get_episode
from app.agents.academy.characters import bot_id_for
from app.agents.academy.harness import opening_turns, reply_turns
from app.agents.academy.talk import build_user_line
from app.db.models import AcademyRoom
from app.services.academy.bots import remember_session
from app.services.academy.errors import AcademyError
from app.services.academy.profile import talent_badge
from app.services.academy.progress import require_unlocked

log = logging.getLogger(__name__)


def _room(db: Session, user_id: int, episode_id: str) -> AcademyRoom:
    row = db.scalar(
        select(AcademyRoom).where(
            AcademyRoom.child_user_id == user_id,
            AcademyRoom.episode_id == episode_id,
        )
    )
    if row is None:
        row = AcademyRoom(child_user_id=user_id, episode_id=episode_id, messages=[], user_turns=0)
        db.add(row)
        db.flush()
    if row.messages is None:
        row.messages = []
    return row


def _tail(episode: Episode) -> dict:
    return {
        "chips": list(episode.chips),
        "nudge": {
            "text": f"善雨导师提醒：聊完记得完成今晚训练——{episode.task}，到大宇智能体打卡。",
            "href": "train.html",
        },
    }


def _memorize(db: Session, user_id: int, episode_id: str, lines: list[dict]) -> None:
    speakers = []
    for row in lines:
        who = row.get("who")
        if who and who != "me" and who not in speakers:
            speakers.append(who)
    for who in speakers:
        remember_session(
            db,
            bot_id_for(who),
            child_user_id=user_id,
            episode_id=episode_id,
            lines=lines,
        )


def _require_episode(episode_id: str) -> Episode:
    episode = get_episode(episode_id)
    if not episode:
        raise AcademyError("没有这一集", 404)
    return episode


def _save_detached(user_id: int, episode_id: str, turns: list[dict]) -> None:
    """请求已经取消时，用自己的会话把角色台词补上。不复用请求里的 Session。"""
    if not turns:
        return
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        room = _room(db, user_id, episode_id)
        history = list(room.messages or [])
        if history[-len(turns):] == list(turns):
            return
        history.extend(turns)
        room.messages = history[-40:]
        _memorize(db, user_id, episode_id, history[-12:])
        db.commit()
    except Exception:
        log.exception("讨论区补写失败")
        db.rollback()
    finally:
        db.close()


def _on_left(done: asyncio.Task, user_id: int, episode_id: str) -> None:
    if done.cancelled():
        return
    error = done.exception()
    if error:
        log.warning("退出后这一轮没写完：%s", type(error).__name__)
        return
    _save_detached(user_id, episode_id, list(done.result() or []))


async def _keep_running(work, user_id: int, episode_id: str):
    """模型还在说时用户关掉页面，这一轮继续跑完并落库。"""
    task = asyncio.create_task(work)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        task.add_done_callback(lambda done: _on_left(done, user_id, episode_id))
        raise


async def open_room(db: Session, user_id: int, episode_id: str) -> dict:
    episode = _require_episode(episode_id)
    require_unlocked(db, user_id, episode.id)
    room = _room(db, user_id, episode.id)
    existing = list(room.messages or [])
    tail = _tail(episode)
    if existing:
        db.commit()
        turns = list(room.messages or [])
        return {"replay": True, "turns": turns, **tail}
    _, talent_name, _ = talent_badge(db, user_id)
    turns = await _keep_running(
        opening_turns(
            episode_id=episode.id,
            episode_title=f"{episode.id} {episode.title}",
            task=episode.task,
            child_talent=talent_name,
            child_user_id=user_id,
        ),
        user_id,
        episode.id,
    )
    room.messages = list(turns)
    _memorize(db, user_id, episode.id, turns)
    db.commit()
    return {"replay": False, "turns": turns, **tail}


async def chat(
    db: Session,
    user_id: int,
    episode_id: str,
    text: str,
    mention: str | None = None,
    quote: dict | None = None,
    sticker: str | None = None,
) -> dict:
    episode = _require_episode(episode_id)
    require_unlocked(db, user_id, episode.id)
    row = build_user_line(text, mention, quote, sticker)
    if not row:
        raise AcademyError("先说一句")
    content = row["text"]
    room = _room(db, user_id, episode.id)
    history = list(room.messages or [])
    last_who = next(
        (str(row["who"]) for row in reversed(history) if row.get("who") and row.get("who") != "me"),
        None,
    )
    _, talent_name, _ = talent_badge(db, user_id)
    user_turns = int(room.user_turns or 0) + 1
    prior = list(history)
    history = prior + [row]
    room.messages = history[-40:]
    room.user_turns = user_turns
    db.commit()
    turns = await _keep_running(
        reply_turns(
            content,
            episode_id=episode.id,
            episode_title=f"{episode.id} {episode.title}",
            task=episode.task,
            child_talent=talent_name,
            prior=prior,
            last_who=last_who,
            user_turns=user_turns,
            child_user_id=user_id,
            mention=row.get("mention"),
            quote=row.get("quote"),
        ),
        user_id,
        episode.id,
    )
    history.extend(turns)
    room.messages = history[-40:]
    _memorize(db, user_id, episode.id, history[-12:])
    db.commit()
    show_nudge = user_turns >= 3 or any(word in content for word in ("打卡", "训练", "站桩"))
    return {"turns": turns, "nudge": _tail(episode)["nudge"] if show_nudge else None}
