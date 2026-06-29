"""开发者虚拟时钟 — 仅 JNAO_DEV_MODE=1 时生效，写入 profile_json.dev"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import is_dev_api_enabled
from app.db.models import ChildUser
from app.services.training_day import TZ, training_now


def get_time_override(db: Session, child_user_id: int) -> datetime | None:
    if not is_dev_api_enabled():
        return None
    user = db.get(ChildUser, child_user_id)
    if not user or not isinstance(user.profile_json, dict):
        return None
    raw = (user.profile_json.get("dev") or {}).get("time_override_iso")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt
    except ValueError:
        return None


def set_time_override(db: Session, child_user_id: int, moment: datetime | None) -> None:
    if not is_dev_api_enabled():
        return
    user = db.get(ChildUser, child_user_id)
    if not user:
        return
    profile = dict(user.profile_json or {})
    dev = dict(profile.get("dev") or {})
    if moment is None:
        dev.pop("time_override_iso", None)
    else:
        dev["time_override_iso"] = moment.astimezone(TZ).isoformat()
    if dev:
        profile["dev"] = dev
    else:
        profile.pop("dev", None)
    user.profile_json = profile
    flag_modified(user, "profile_json")


def clear_time_override(db: Session, child_user_id: int) -> None:
    set_time_override(db, child_user_id, None)


def resolve_training_now(db: Session, child_user_id: int | None = None) -> datetime:
    if child_user_id is not None:
        override = get_time_override(db, child_user_id)
        if override is not None:
            return override
    return training_now()
