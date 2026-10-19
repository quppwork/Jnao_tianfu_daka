"""成人报告正文切片 — 把 `report_json` 压成可进 system 上下文的短片段。

只做「读」：不改报告、不落库、不生成结论。切片是这份报告的事实来源，
模型回答分数/五维/状态时以它为准，不再回「还没拿到数据」。
"""

from __future__ import annotations

import json
import re
from typing import Any

MAX_CONTEXT_CHARS = 900

# 五者：报告里 AttributeJs 的键
WUZHE_ORDER = ("学者", "思者", "行者", "德者", "赢者")

_TALENT_CHARS = "学思行德赢"


def _strip_html(text: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = re.sub(r"[ \t]{2,}", " ", s)
    return re.sub(r"\s*\n\s*", " ", s).strip()


def _clip(text: str, n: int) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: max(0, n - 1)].rstrip() + "…"


def _split_check_talent(raw: Any) -> tuple[str, str]:
    """`check_talent` 兼容三种：['学者','思者'] / '学者偏思者' / '思德'。"""
    if isinstance(raw, list) and raw:
        first = str(raw[0] or "").strip()
        second = str(raw[1] or "").strip() if len(raw) > 1 else ""
        return first, second
    text = str(raw or "").strip()
    if not text:
        return "", ""
    if "偏" in text:
        head, _, tail = text.partition("偏")
        return head.strip(), tail.strip()
    if len(text) == 2 and all(ch in _TALENT_CHARS for ch in text):
        return f"{text[0]}者", f"{text[1]}者"
    return text, ""


def _wuzhe_scores(report: dict[str, Any]) -> str:
    raw = report.get("AttributeJs")
    data: dict[str, Any] = {}
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except (TypeError, ValueError):
            data = {}
    elif isinstance(raw, dict):
        data = raw
    if not data:
        return ""
    parts = [f"{name}{data[name]}" for name in WUZHE_ORDER if name in data]
    return " / ".join(parts)


def _ability_line(report: dict[str, Any]) -> str:
    results = report.get("results") if isinstance(report.get("results"), dict) else {}
    rows = results.get("Ability") if isinstance(results.get("Ability"), list) else []
    parts: list[str] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("abilityName") or "").strip()
        if not name:
            continue
        value = row.get("value")
        grade = row.get("grade")
        seg = name
        if isinstance(value, (int, float)):
            seg += f" {int(value)}"
        if isinstance(grade, (int, float)) and int(grade) > 0:
            seg += f"（{int(grade)}级）"
        parts.append(seg)
    return "｜".join(parts)


def build_report_context(
    report_json: dict[str, Any] | None,
    talent_primary: str | None = None,
    *,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """返回可直接拼进 system_extra 的切片文本；无内容返回空串。"""
    report = report_json if isinstance(report_json, dict) else {}
    if not report:
        return ""
    results = report.get("results") if isinstance(report.get("results"), dict) else {}
    talent_block = results.get("Talent") if isinstance(results.get("Talent"), dict) else {}
    state_block = results.get("State") if isinstance(results.get("State"), dict) else {}
    attr_block = results.get("Attribute") if isinstance(results.get("Attribute"), dict) else {}
    type_block = results.get("TalentType") if isinstance(results.get("TalentType"), dict) else {}

    main, second = _split_check_talent(report.get("check_talent"))
    main = main or str(talent_primary or report.get("talent") or "").strip()
    if main and not second and str(report.get("talent") or "").strip() not in ("", main):
        alt = str(report.get("talent")).strip()
        if alt and alt != main and len(alt) == 2 and all(c in _TALENT_CHARS for c in alt):
            second = f"{alt[1]}者"

    lines: list[str] = []
    if main:
        head = f"报告中标注天赋：{main}"
        if second and second != main:
            head += f"（副 {second}）"
        lines.append(head)

    wuzhe = _wuzhe_scores(report)
    if wuzhe:
        lines.append(f"五者分值：{wuzhe}")

    ability = _ability_line(report)
    if ability:
        lines.append(f"五维能量：{ability}")

    state_name = str(state_block.get("name") or "").strip()
    if state_name:
        lines.append(f"当前状态：{state_name}")

    type_name = str(type_block.get("name") or "").strip()
    if type_name:
        lines.append(f"天赋类型：{type_name}")

    talent_desp = _clip(_strip_html(str(talent_block.get("desp") or "")), 220)
    if talent_desp:
        lines.append(f"天赋能力解读：{talent_desp}")

    if not talent_desp:
        attr_desp = _clip(_strip_html(str(attr_block.get("desp") or "")), 160)
        if attr_desp:
            lines.append(f"属性说明：{attr_desp}")

    body = "\n".join(lines).strip()
    return _clip(body, max_chars)
