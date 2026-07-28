"""工具：有效天赋报告摘要（只读，供轻量解读；非整包 report_json）。"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.agents.guide.tools import register

_MAX_FIELD = 400
_MAX_TOTAL = 1400


def _strip_html(text: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"\s+\n", "\n", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def _clip(text: str, n: int = _MAX_FIELD) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _parse_talent_desp(html: str) -> dict:
    """对齐报告页 parsedTalent 的轻量抽取。"""
    raw = html or ""
    if not raw:
        return {"ability_desc": "", "words_for_you": "", "golden_advice": []}
    words_idx = raw.find("想对你说的话")
    golden_idx = raw.find("三条黄金建议")
    ability = ""
    words = ""
    advice: list[str] = []
    if words_idx >= 0:
        ability = _strip_html(
            re.sub(
                r"<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*</p>",
                "",
                raw[:words_idx],
                flags=re.I,
            )
        )
        if golden_idx >= 0:
            words = _strip_html(raw[words_idx:golden_idx])
            block = _strip_html(raw[golden_idx:]).replace("三条黄金建议", "").strip(" ：:")
            for part in re.split(r"(?=\d+\.)", block):
                c = re.sub(r"^\d+\.\s*", "", part).strip()
                if c:
                    advice.append(_clip(c, 120))
        else:
            words = _strip_html(raw[words_idx:])
    else:
        ability = _strip_html(
            re.sub(
                r"<p[^>]*>\s*<strong>【?天赋能力解读】?<\/strong>\s*</p>",
                "",
                raw,
                flags=re.I,
            )
        )
    return {
        "ability_desc": _clip(ability),
        "words_for_you": _clip(words),
        "golden_advice": advice[:3],
    }


@register("get_talent_report_summary")
def get_talent_report_summary(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    from app.agents.shared.talent import talent_coaching_hint
    from app.core.talent_mapping import parse_check_talent
    from app.services.assessment_service import (
        get_assessment_by_id,
        get_latest_assessment,
        resolve_effective_talent,
    )

    eff = resolve_effective_talent(db, child_user_id)
    if not eff or not (eff.get("has_assessment") or eff.get("talent_code")):
        return {
            "has_assessment": False,
            "message": "尚未完成天赋测评，请先去做天赋测试。",
        }

    report: dict = {}
    assessment_id = eff.get("assessment_id")
    row = None
    if assessment_id:
        row = get_assessment_by_id(db, int(assessment_id), child_user_id)
    if row is None and eff.get("talent_source") == "assessment":
        row = get_latest_assessment(db, child_user_id)
    if row is not None:
        report = row.report_json if isinstance(row.report_json, dict) else {}
        assessment_id = row.id

    primary = (
        eff.get("talent_primary")
        or (row.talent_primary if row else None)
        or report.get("talent")
        or ""
    )
    check = report.get("check_talent")
    _, secondary = parse_check_talent(check)
    results = report.get("results") if isinstance(report.get("results"), dict) else {}
    talent_block = results.get("Talent") if isinstance(results.get("Talent"), dict) else {}
    state_block = results.get("State") if isinstance(results.get("State"), dict) else {}
    attr = results.get("Attribute") if isinstance(results.get("Attribute"), dict) else {}

    parsed = _parse_talent_desp(str(talent_block.get("desp") or ""))
    state_name = state_block.get("name") or ""
    state_summary = _clip(_strip_html(str(state_block.get("desp") or "")), 280)
    attr_desp = _clip(_strip_html(str(attr.get("desp") or "")), 200)

    out = {
        "has_assessment": True,
        "assessment_id": assessment_id,
        "talent_primary": primary,
        "talent_secondary": secondary or "",
        "talent_source": eff.get("talent_source"),
        "talent_locked": bool(eff.get("talent_locked")),
        "state_name": state_name,
        "state_summary": state_summary,
        "attribute_summary": attr_desp,
        "ability_desc": parsed["ability_desc"],
        "words_for_you": parsed["words_for_you"],
        "golden_advice": parsed["golden_advice"],
        "coach_hint": talent_coaching_hint(primary, report if report else None),
        "note": "以上为有效天赋报告摘要；完整图表与原文请引导用户去「天赋报告」页查看。勿编造摘要未出现的内容。",
    }

    # 控制总体积
    blob = str(out)
    if len(blob) > _MAX_TOTAL:
        out["ability_desc"] = _clip(out["ability_desc"], 200)
        out["words_for_you"] = _clip(out["words_for_you"], 160)
        out["state_summary"] = _clip(out["state_summary"], 160)
    return out
