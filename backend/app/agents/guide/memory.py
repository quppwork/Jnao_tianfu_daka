"""Guide Agent 记忆 — 会话助手 + 开场按日缓存（含情境快照）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ChildUser, GuideSession

# 进程内缓存：key = f"{uid}:{training_day}"
_BOOTSTRAP_CACHE: dict[str, dict] = {}


def truncate_history(messages: list[dict], *, max_turns: int = 12) -> list[dict]:
    if max_turns <= 0 or len(messages) <= max_turns:
        return list(messages)
    return list(messages[-max_turns:])


def session_to_history(session: GuideSession | None) -> list[dict]:
    if not session:
        return []
    return [{"role": m.role, "content": m.content} for m in session.messages]


def _cache_key(child_user_id: int, training_day: str) -> str:
    return f"{child_user_id}:{training_day}"


def get_cached_welcome(db: Session, child_user_id: int, training_day: str) -> dict | None:
    key = _cache_key(child_user_id, training_day)
    hit = _BOOTSTRAP_CACHE.get(key)
    if hit:
        return hit
    # 回退 profile_json，跨进程重启仍可用
    child = db.get(ChildUser, child_user_id)
    if not child or not isinstance(child.profile_json, dict):
        return None
    blob = (child.profile_json.get("guide_bootstrap") or {})
    if blob.get("training_day") == training_day and blob.get("welcome"):
        _BOOTSTRAP_CACHE[key] = {
            "situation": blob.get("situation"),
            "next_action": blob.get("next_action"),
            "welcome": blob["welcome"],
            "source": blob.get("source") or "cache",
            "snapshot": blob.get("snapshot") or {},
        }
        return _BOOTSTRAP_CACHE[key]
    return None


def set_cached_welcome(
    db: Session,
    child_user_id: int,
    training_day: str,
    payload: dict,
) -> None:
    key = _cache_key(child_user_id, training_day)
    entry = {
        "situation": payload.get("situation"),
        "next_action": payload.get("next_action"),
        "welcome": payload.get("welcome"),
        "source": payload.get("source"),
        "snapshot": payload.get("snapshot") or {},
    }
    _BOOTSTRAP_CACHE[key] = entry

    child = db.get(ChildUser, child_user_id)
    if not child:
        return
    pj = dict(child.profile_json or {})
    pj["guide_bootstrap"] = {
        "training_day": training_day,
        **entry,
    }
    child.profile_json = pj
    try:
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(child, "profile_json")
        db.commit()
    except Exception:
        db.rollback()


def clear_bootstrap_cache(child_user_id: int | None = None) -> None:
    """测试或强制刷新辅助。"""
    if child_user_id is None:
        _BOOTSTRAP_CACHE.clear()
        return
    prefix = f"{child_user_id}:"
    for k in list(_BOOTSTRAP_CACHE):
        if k.startswith(prefix):
            del _BOOTSTRAP_CACHE[k]
