"""从 OSS 索引按天赋聚合（三系列合并）— 输出第一课结构

用法: python scripts/oss_structure_report.py
输出:
  docs/data/oss_by_talent.json      — 按天赋聚合（排课视角）
  docs/data/oss_structure_by_talent.json — 兼容旧路径
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "data" / "oss_yinpin_index.json"
OUT_TALENT = ROOT / "docs" / "data" / "oss_by_talent.json"
OUT_LEGACY = ROOT / "docs" / "data" / "oss_structure_by_talent.json"

TALENT_ORDER = ["学者", "思者", "行者", "德者", "赢者"]
TALENT_CODE = {"学者": 1, "思者": 2, "行者": 3, "德者": 4, "赢者": 5}
TAG_MAP = {"xue": "学者", "si": "思者", "xing": "行者", "de": "德者", "ying": "赢者"}

SKILL_ALIASES = {
    "影像记忆": "影像追忆",
    "超脑速读": "超脑阅读",
    "绘画灵感": "天赋绘画",
}

FILENAME_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)"
    r"(?P<skill>影像追忆|影像记忆|扫描速记|极速学习|极速运算|超脑速读|精力恢复|高效作业|"
    r"数学奥秘|文科奥秘|理科奥秘|英语奥秘|绘画灵感|音乐灵感|我是冠军|棋类专注|考前减压)"
    r"(?:(?P<stage>\d+)阶段(?P<part>\d+))?"
    r"\.mp3$",
    re.IGNORECASE,
)


def parse_file_name(file_name: str) -> dict | None:
    m = FILENAME_RE.match(file_name)
    if not m:
        return None
    skill_raw = m.group("skill")
    skill = SKILL_ALIASES.get(skill_raw, skill_raw)
    stage = int(m.group("stage") or 0)
    part = int(m.group("part") or 1)
    if skill_raw == "超脑速读" and stage == 0:
        stage, part = 1, 1
    return {
        "talent": m.group("talent"),
        "skill": skill,
        "skill_oss": skill_raw,
        "stage": stage,
        "part": part,
        "file_name": file_name,
    }


def main() -> None:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    by_talent: dict[str, list[dict]] = defaultdict(list)
    unparsed: list[str] = []

    for row in data.get("items", []):
        key = row.get("key", "")
        parts = key.split("/")
        series = parts[1] if len(parts) > 1 else "unknown"
        tag = parts[2] if len(parts) > 2 else ""
        parsed = parse_file_name(row.get("file_name", ""))
        if not parsed:
            unparsed.append(key)
            continue
        by_talent[parsed["talent"]].append(
            {
                **parsed,
                "series": series,
                "oss_key": key,
                "url": row.get("url"),
                "tag_folder": tag,
            }
        )

    report = {
        "model": "by_talent",
        "description": "三系列 OSS 按天赋合并；排课按 talent_code 查混合池，按技能阶段混合推送",
        "source_index": str(INDEX),
        "total_oss_files": data.get("total"),
        "unparsed_count": len(unparsed),
        "unparsed_sample": unparsed[:20],
        "talents": {},
    }

    for talent in TALENT_ORDER:
        items = by_talent.get(talent, [])
        if not items:
            continue
        by_skill: dict[str, list[dict]] = defaultdict(list)
        by_series: dict[str, int] = defaultdict(int)
        for it in items:
            by_skill[it["skill"]].append(it)
            by_series[it["series"]] += 1

        skills_out = {}
        for skill, lst in sorted(by_skill.items()):
            lst.sort(key=lambda x: (x["stage"], x["part"], x["file_name"]))
            first = lst[0]
            skills_out[skill] = {
                "skill_canonical": skill,
                "skill_oss": first["skill_oss"],
                "first_stage": first["stage"],
                "first_part": first["part"],
                "first_file": first["file_name"],
                "first_oss_key": first["oss_key"],
                "first_series": first["series"],
                "total_lessons": len(lst),
                "series_sources": sorted({x["series"] for x in lst}),
            }

        report["talents"][talent] = {
            "talent_code": TALENT_CODE[talent],
            "total_files": len(items),
            "files_by_series": dict(sorted(by_series.items())),
            "skills": skills_out,
            "skill_names": sorted(skills_out.keys()),
        }

    OUT_TALENT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_LEGACY.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {OUT_TALENT}")
    print(f"Total OSS: {report['total_oss_files']}, unparsed: {report['unparsed_count']}")
    for talent in TALENT_ORDER:
        t = report["talents"].get(talent)
        if not t:
            continue
        print(f"\n【{talent}】共 {t['total_files']} 个文件 | 系列分布: {t['files_by_series']}")
        for sk, info in t["skills"].items():
            st, pt = info["first_stage"], info["first_part"]
            label = f"{st}阶段{pt}" if st else "单课"
            src = ",".join(info["series_sources"])
            print(f"  · {sk}({label}) ×{info['total_lessons']}  ← {src}")


if __name__ == "__main__":
    main()
