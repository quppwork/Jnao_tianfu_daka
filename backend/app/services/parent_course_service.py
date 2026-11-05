"""家长课堂目录（独立域：只读 catalog；进度/正片后续扩展）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from config.loader import load_parent_courses


def _progress_map(db: Session, parent_id: int) -> dict[str, dict[str, Any]]:
    """profile_json.parent_courses[course_id] = { done: int }"""
    from app.db.models import ChildUser

    user = db.get(ChildUser, parent_id)
    if not user or not isinstance(user.profile_json, dict):
        return {}
    raw = user.profile_json.get("parent_courses")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for cid, row in raw.items():
        if not isinstance(row, dict):
            continue
        try:
            done = max(0, int(row.get("done") or 0))
        except (TypeError, ValueError):
            done = 0
        out[str(cid)] = {"done": done}
    return out


def list_courses(db: Session, parent_id: int) -> dict[str, Any]:
    cfg = load_parent_courses() or {}
    progress = _progress_map(db, parent_id)
    items: list[dict[str, Any]] = []
    for raw in cfg.get("courses") or []:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or "").strip()
        if not cid:
            continue
        lessons = [str(x) for x in (raw.get("lessons") or []) if str(x).strip()]
        total = len(lessons)
        done = min(total, int((progress.get(cid) or {}).get("done") or 0))
        now = done if done < total else (total - 1 if total else -1)
        if done <= 0:
            now = 0 if total else -1
        intro = raw.get("intro") if isinstance(raw.get("intro"), dict) else {}
        cover = str(intro.get("cover") or "").strip()
        items.append(
            {
                "id": cid,
                "icon": str(raw.get("icon") or "📚"),
                "name": str(raw.get("name") or cid),
                "sub": str(raw.get("sub") or ""),
                "lessons": lessons,
                "total": total,
                "done": done,
                "now": now,
                "percent": round(done / total * 100) if total else 0,
                "playback_ready": False,
                "intro": {
                    "cover": cover,
                    "title": str(intro.get("title") or ""),
                    "duration": str(intro.get("duration") or ""),
                    "bg": (
                        f"linear-gradient(180deg,rgba(8,10,18,.1),rgba(8,10,18,.68)),"
                        f"url({cover}) center/cover no-repeat"
                        if cover
                        else ""
                    ),
                },
            }
        )
    return {
        "title": str(cfg.get("title") or "家长课堂"),
        "subtitle": str(cfg.get("subtitle") or ""),
        "version": int(cfg.get("version") or 1),
        "courses": items,
        "opened_count": len(items),
        "note": "目录已同步；正片点播与学习进度写入后续开放",
    }
