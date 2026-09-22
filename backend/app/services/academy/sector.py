"""三页视图：频道、历史剧情、课程。只读目录和进度，不调大模型。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.academy.catalog import (
    ACTS,
    CALLIGRAPHY,
    CURRENT_EPISODE_ID,
    EPISODES,
    MIJI,
    OFFERS,
    SWITCHABLE_IDS,
    Episode,
    get_episode,
)
from app.agents.academy.characters import CHARACTERS
from app.agents.academy.packs import get_pack
from app.db.models import AcademyProgress
from app.services.academy import playback, progress as progress_store
from app.services.academy.demo import CAMP
from app.services.academy.profile import talent_badge


def episode_chips(episode: Episode) -> list[str]:
    """用户视角问剧情的快捷提示；优先剧集包。"""
    pack = get_pack(episode.id)
    if pack and pack.chips:
        return list(pack.chips)
    return list(episode.chips)


def episode_status(*, unlocked: bool, media: str, prev_ready: bool, act_locked: bool) -> str:
    if act_locked:
        return "locked"
    if unlocked:
        return "watched"
    if media == "none":
        return "upcoming"
    if prev_ready:
        return "open"
    return "locked"


def _cast(keys: tuple[str, ...]) -> list[dict]:
    out = []
    for key in keys:
        char = CHARACTERS.get(key)
        if char:
            out.append({"key": char.key, "name": char.name, "tag": char.tag})
    return out


def _focus(requested: str | None, rows: dict[str, AcademyProgress]) -> Episode:
    picked = get_episode(requested) if requested else None
    if picked:
        return picked
    for episode in EPISODES.values():
        row = rows.get(episode.id)
        if playback.kind_of(episode) != "none" and not progress_store.is_unlocked(row):
            return episode
    return EPISODES[CURRENT_EPISODE_ID]


def _acts(rows: dict[str, AcademyProgress]) -> list[dict]:
    prev_ready = True
    acts = []
    for act in ACTS:
        episodes = []
        watched = 0
        for episode_id in act.episode_ids:
            episode = EPISODES[episode_id]
            row = rows.get(episode_id)
            media = playback.kind_of(episode)
            status = episode_status(
                unlocked=progress_store.is_unlocked(row),
                media=media,
                prev_ready=prev_ready,
                act_locked=act.locked,
            )
            if status == "watched":
                watched += 1
                prev_ready = True
            elif status == "upcoming":
                prev_ready = prev_ready
            else:
                prev_ready = False
            episodes.append({
                "id": episode.id,
                "title": episode.title,
                "topic": episode.topic,
                "status": status,
                "media": media,
                "playable": media != "none",
                "unlocked": progress_store.is_unlocked(row),
            })
        if act.locked:
            act_status = "lockd"
        elif act.episode_ids and watched == len(act.episode_ids):
            act_status = "done"
        elif watched or any(item["playable"] and not item["unlocked"] for item in episodes):
            act_status = "ing"
        else:
            act_status = "lockd"
        acts.append({
            "no": act.no,
            "name": act.name,
            "range": act.range,
            "poster": act.poster,
            "core": act.core,
            "tag": act.tag,
            "locked": act.locked,
            "status": act_status,
            "watched": watched,
            "total": len(act.episode_ids),
            "episodes": episodes,
        })
    return acts


def _courses(rows: dict[str, AcademyProgress]) -> dict:
    chapters = []
    done = 0
    for title, episode_id in CALLIGRAPHY:
        watched = progress_store.is_unlocked(rows.get(episode_id))
        if watched:
            done += 1
        chapters.append({
            "title": title,
            "episode_id": episode_id,
            "status": "done" if watched else "todo",
        })
    marked = False
    for chapter in chapters:
        if chapter["status"] == "done":
            continue
        chapter["status"] = "now" if not marked else "todo"
        marked = True
    total = len(chapters) or 1
    miji = []
    for name, file, desc, episode_id in MIJI:
        miji.append({
            "name": name,
            "cover": f"/static/dayu/assets/miji/{file}.jpg",
            "desc": desc,
            "episode_id": episode_id,
            "unlocked": progress_store.is_unlocked(rows.get(episode_id)),
        })
    return {
        "enrolled_count": 1,
        "mine": {
            "title": "大书道课程",
            "subtitle": "进度跟书道剧集走；未看的讲次用模拟片",
            "done": done,
            "total": len(CALLIGRAPHY),
            "percent": int(round(done / total * 100)),
            "chapters": chapters,
        },
        "miji": miji,
        "offers": list(OFFERS),
        "camp": dict(CAMP),
    }


def _channel(episode: Episode, row: AcademyProgress | None, *, user_id: int | None = None) -> dict:
    cast = _cast(episode.cast)
    media = playback.kind_of(episode)
    return {
        "id": episode.id,
        "title": episode.title,
        "topic": episode.topic,
        "task": episode.task,
        "channel_name": f"{episode.id} · {episode.title}讨论组",
        "online_count": len(cast),
        "notice": f"频道公告：今晚{episode.task}。——善雨导师",
        "poster": episode.poster,
        "duration_label": playback.duration_label(episode),
        "play_url": playback.play_url(episode, user_id=user_id),
        "media": media,
        "playable": media != "none",
        "unlocked": progress_store.is_unlocked(row),
        "percent": int(row.percent) if row else 0,
        "chips": episode_chips(episode),
        "nudge": {
            "text": f"善雨导师提醒：聊完记得完成今晚训练——{episode.task}，到大宇智能体打卡。",
            "href": "train.html",
        },
        "cast": cast,
    }


def _switchable(rows: dict[str, AcademyProgress], current_id: str) -> list[dict]:
    """频道标题下拉：测试集始终可切；讨论是否解锁仍看 episode.unlocked。"""
    out = []
    for episode_id in SWITCHABLE_IDS:
        episode = EPISODES.get(episode_id)
        if not episode:
            continue
        out.append({
            "id": episode.id,
            "title": episode.title,
            "channel_name": f"{episode.id} · {episode.title}讨论组",
            "unlocked": True,
            "current": episode.id == current_id,
        })
    return out


def get_sector(db: Session, user_id: int, episode_id: str | None = None) -> dict:
    progress_store.seed_demo_if_empty(db, user_id)
    rows = progress_store.load_map(db, user_id)
    badge, talent_name, tier = talent_badge(db, user_id)
    focus = _focus(episode_id, rows)
    return {
        "user_id": user_id,
        "badge": badge,
        "talent_primary": talent_name,
        "overall_tier": tier,
        "episode": _channel(focus, rows.get(focus.id), user_id=user_id),
        "switchable": _switchable(rows, focus.id),
        "acts": _acts(rows),
        "courses": _courses(rows),
    }
