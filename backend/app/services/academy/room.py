"""讨论区。只负责落库和调用 harness，不组装三页目录。"""

from __future__ import annotations

import asyncio
import logging
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.academy.catalog import Episode, get_episode
from app.agents.academy.characters import bot_id_for
from app.agents.academy.affect import step
from app.agents.academy.harness import opening_turns, reply_turns, route_topic
from app.agents.academy.talk import annotate_for_model, build_user_line
from app.db.models import AcademyRoom
from app.services.academy.bots import remember_session
from app.services.academy.errors import AcademyError
from app.services.academy.guide import today_training
from app.services.academy.profile import talent_badge
from app.services.academy.progress import require_unlocked

log = logging.getLogger(__name__)

# 同一用户同一集共用一个 opening Task，断开重进也不二次打模型
_open_inflight: dict[tuple[int, str], asyncio.Task] = {}


def _open_key(user_id: int, episode_id: str) -> tuple[int, str]:
    return (int(user_id), str(episode_id).upper())


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


def _tail(episode: Episode, trained: bool) -> dict:
    from app.services.academy.sector import episode_chips

    body = {
        "chips": episode_chips(episode),
        "training_done": trained,
        "nudge": None,
    }
    if not trained:
        body["nudge"] = {
            "text": f"今天的训练还没完成。去今日修炼做完再回来聊——{episode.task}。",
            "href": "train.html",
        }
    return body


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


def _peek_messages(user_id: int, episode_id: str) -> list[dict]:
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        room = _room(db, user_id, episode_id)
        return list(room.messages or [])
    finally:
        db.close()


def _persist_opening(user_id: int, episode_id: str, turns: list[dict]) -> list[dict]:
    """LLM 结束后用独立会话落库；若并发已写入则直接回放。"""
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        room = _room(db, user_id, episode_id)
        existing = list(room.messages or [])
        if existing:
            return existing
        room.messages = list(turns or [])
        if turns:
            _memorize(db, user_id, episode_id, turns)
        db.commit()
        return list(turns or [])
    except Exception:
        log.exception("讨论区开场落库失败")
        db.rollback()
        return list(turns or [])
    finally:
        db.close()


def _append_reply_detached(user_id: int, episode_id: str, turns: list[dict]) -> None:
    if not turns:
        return
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        room = _room(db, user_id, episode_id)
        history = list(room.messages or [])
        history.extend(turns)
        room.messages = history[-40:]
        _memorize(db, user_id, episode_id, history[-12:])
        db.commit()
    except Exception:
        log.exception("讨论区回复落库失败")
        db.rollback()
    finally:
        db.close()


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


def _release_request_db(db: Session) -> None:
    """长 LLM 前释放请求 Session，避免 SQLite 连接占住挡住 sector/progress。"""
    try:
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    try:
        db.close()
    except Exception:
        pass


async def open_room(db: Session, user_id: int, episode_id: str) -> dict:
    from app.agents.academy.perception import messages_fit_episode

    episode = _require_episode(episode_id)
    require_unlocked(db, user_id, episode.id)
    room = _room(db, user_id, episode.id)
    existing = list(room.messages or [])
    # 串集旧稿（如 E14 里还是五兽桩）丢掉重开
    if existing and not messages_fit_episode(episode.id, existing):
        room.messages = []
        room.user_turns = 0
        existing = []
        db.commit()
    trained = bool(today_training(db, user_id).get("done"))
    tail = _tail(episode, trained)
    if existing:
        _release_request_db(db)
        return {"replay": True, "turns": existing, **tail}
    _, talent_name, _ = talent_badge(db, user_id)
    ep_id = episode.id
    ep_title = f"{episode.id} {episode.title}"
    ep_task = episode.task
    # 释放连接后再跑 opening（多角色串行 LLM 可达数十秒）
    _release_request_db(db)

    key = _open_key(user_id, ep_id)
    inflight = _open_inflight.get(key)
    if inflight is not None and not inflight.done():
        try:
            saved = await asyncio.shield(inflight)
        except asyncio.CancelledError:
            raise
        except Exception:
            saved = _peek_messages(user_id, ep_id)
        if not saved:
            saved = _peek_messages(user_id, ep_id)
        return {"replay": True, "turns": list(saved or []), **tail}

    again = _peek_messages(user_id, ep_id)
    if again and messages_fit_episode(ep_id, again):
        return {"replay": True, "turns": again, **tail}
    if again and not messages_fit_episode(ep_id, again):
        from app.db.session import get_session_factory

        wipe = get_session_factory()()
        try:
            row = _room(wipe, user_id, ep_id)
            row.messages = []
            row.user_turns = 0
            wipe.commit()
        finally:
            wipe.close()

    async def _generate() -> list[dict]:
        turns = await opening_turns(
            episode_id=ep_id,
            episode_title=ep_title,
            task=ep_task,
            child_talent=talent_name,
            child_user_id=user_id,
            training_done=trained,
        )
        return _persist_opening(user_id, ep_id, list(turns or []))

    gen_task = asyncio.create_task(_generate())
    _open_inflight[key] = gen_task

    def _clear(done: asyncio.Task, *, _k: tuple[int, str] = key) -> None:
        if _open_inflight.get(_k) is done:
            _open_inflight.pop(_k, None)

    gen_task.add_done_callback(_clear)

    try:
        saved = await asyncio.shield(gen_task)
        return {"replay": False, "turns": list(saved or []), **tail}
    except asyncio.CancelledError:
        # 生成继续跑完并落库；下次 open 会挂上同一 Task 或直接 replay
        raise


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
    model_text = annotate_for_model(row)
    room = _room(db, user_id, episode.id)
    history = list(room.messages or [])
    last_who = next(
        (str(item["who"]) for item in reversed(history) if item.get("who") and item.get("who") != "me"),
        None,
    )
    _, talent_name, _ = talent_badge(db, user_id)
    trained = bool(today_training(db, user_id).get("done"))
    affect = step(room.affect if isinstance(room.affect, dict) else None, model_text)
    room.affect = affect
    user_turns = int(room.user_turns or 0) + 1
    prior = list(history)
    history = prior + [row]
    room.messages = history[-40:]
    room.user_turns = user_turns
    nudge = _tail(episode, trained)["nudge"]
    # 用户句先落库并释放连接，再等模型
    _release_request_db(db)

    turns: list[dict] = []
    try:
        turns = await _keep_running(
            reply_turns(
                model_text,
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
                topic=route_topic(model_text),
                affect=affect,
                training_done=trained,
                nudge_train=(not trained) and random.random() < 0.22,
            ),
            user_id,
            episode.id,
        )
    except Exception:
        log.exception("讨论区模型失败，本轮不返回假台词")
        turns = []
    if turns:
        _append_reply_detached(user_id, episode.id, turns)
    return {"turns": turns, "nudge": nudge, "training_done": trained}
