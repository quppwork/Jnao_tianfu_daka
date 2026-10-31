"""单集观看进度。解锁只认本表，模拟记录也写进同一张表。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.academy.catalog import EPISODES, get_episode
from app.agents.academy.harness import should_unlock
from app.db.models import AcademyProgress
from app.services.academy.demo import DEMO_WATCHED_IDS
from app.services.academy.errors import AcademyError


def load_map(db: Session, user_id: int) -> dict[str, AcademyProgress]:
    rows = db.scalars(
        select(AcademyProgress).where(AcademyProgress.child_user_id == user_id)
    ).all()
    return {row.episode_id: row for row in rows}


def seed_demo_if_empty(db: Session, user_id: int) -> bool:
    """缺记录的模拟集写入已看完。已有的集不覆盖。"""
    rows = load_map(db, user_id)
    added = False
    for episode_id in DEMO_WATCHED_IDS:
        if episode_id in rows or episode_id not in EPISODES:
            continue
        db.add(AcademyProgress(
            child_user_id=user_id,
            episode_id=episode_id,
            percent=100,
            unlocked=1,
        ))
        added = True
    if added:
        db.commit()
    return added


def is_unlocked(row: AcademyProgress | None) -> bool:
    return bool(row and row.unlocked)


def report(
    db: Session,
    user_id: int,
    episode_id: str,
    *,
    percent: float | None = None,
    position_sec: float | None = None,
    duration_sec: float | None = None,
) -> dict:
    episode = get_episode(episode_id)
    if not episode:
        raise AcademyError("没有这一集", 404)
    if duration_sec and duration_sec > 0 and position_sec is not None:
        percent = max(0.0, min(100.0, float(position_sec) / float(duration_sec) * 100))
    if percent is None:
        raise AcademyError("缺少观看进度")
    percent_i = max(0, min(100, int(percent)))
    row = db.scalar(
        select(AcademyProgress).where(
            AcademyProgress.child_user_id == user_id,
            AcademyProgress.episode_id == episode.id,
        )
    )
    if row is None:
        row = AcademyProgress(child_user_id=user_id, episode_id=episode.id, percent=0, unlocked=0)
        db.add(row)
    if percent_i > int(row.percent or 0):
        row.percent = percent_i
    if should_unlock(row.percent):
        row.unlocked = 1
    db.commit()
    return {
        "episode_id": episode.id,
        "percent": int(row.percent or 0),
        "unlocked": bool(row.unlocked),
    }


def require_unlocked(db: Session, user_id: int, episode_id: str) -> None:
    row = db.scalar(
        select(AcademyProgress).where(
            AcademyProgress.child_user_id == user_id,
            AcademyProgress.episode_id == episode_id,
        )
    )
    if not is_unlocked(row):
        raise AcademyError("看完正片才能加入讨论", 403)
