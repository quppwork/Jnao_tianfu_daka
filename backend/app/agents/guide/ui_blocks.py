"""Guide Generative UI（R6）— 从工具结果组装可渲染 blocks。"""

from __future__ import annotations

from typing import Any

_STATUS_LABEL = {
    "pending": "未开始",
    "in_progress": "进行中",
    "done": "已完成",
    "completed": "已完成",
}


def _brief_today_plan(result: dict) -> dict[str, Any] | None:
    today = result.get("today") if isinstance(result.get("today"), dict) else {}
    if not today.get("exists"):
        return {
            "type": "today_summary",
            "title": "今日训练",
            "items": [{"label": "方案", "value": "暂无今日方案"}],
        }
    status = str(today.get("status") or "")
    status_l = _STATUS_LABEL.get(status, status or "—")
    done = today.get("done_count")
    total = today.get("item_count")
    mins = today.get("planned_minutes")
    items = []
    if mins is not None:
        items.append({"label": "计划时长", "value": f"{mins} 分钟"})
    if total is not None:
        items.append({"label": "完成进度", "value": f"{done or 0}/{total}"})
    items.append({"label": "状态", "value": status_l})
    return {"type": "today_summary", "title": "今日训练", "items": items}


def _brief_skill_progress(result: dict) -> dict[str, Any] | None:
    skills = result.get("skills") if isinstance(result.get("skills"), dict) else {}
    rows = []
    for name, sd in list(skills.items())[:8]:
        if not isinstance(sd, dict):
            continue
        tier = sd.get("tier")
        if tier is None:
            continue
        rows.append({"name": str(name), "tier": int(tier)})
    if not rows:
        return None
    rows.sort(key=lambda x: (x["tier"], x["name"]))
    return {
        "type": "skill_snapshot",
        "title": "技能档位（仅供参考）",
        "overall_tier": result.get("overall_tier"),
        "items": rows,
    }


def _brief_day_checkin(result: dict) -> dict[str, Any] | None:
    qd = str(result.get("query_date") or "")[:10]
    skills = [str(s) for s in (result.get("skills") or []) if s][:8]
    count = int(result.get("record_count") or 0)
    msg = result.get("message")
    return {
        "type": "checkin_day",
        "title": "打卡摘要",
        "date": qd or None,
        "record_count": count,
        "skills": skills,
        "note": str(msg) if msg else None,
    }


def result_brief_for_tool(name: str, result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict) or result.get("error"):
        return None
    if name == "get_today_plan":
        return _brief_today_plan(result)
    if name == "get_skill_progress":
        return _brief_skill_progress(result)
    if name == "get_day_checkin_detail":
        return _brief_day_checkin(result)
    return None


def build_ui_blocks(tools_used: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """从 tools_used[].result_brief 去重组装 blocks（最多 3 个）。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for t in tools_used or []:
        if not isinstance(t, dict) or not t.get("ok"):
            continue
        brief = t.get("result_brief")
        if not isinstance(brief, dict):
            continue
        btype = str(brief.get("type") or "")
        if not btype or btype in seen:
            continue
        seen.add(btype)
        out.append(brief)
        if len(out) >= 3:
            break
    return out
