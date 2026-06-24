"""Build catalog JSON from locally downloaded 小鹅通「脑力奥秘」 MP3 files.

Usage:
  python scripts/build_xet_brain_power_catalog.py "D:/downloads/脑力奥秘"
  python scripts/build_xet_brain_power_catalog.py "D:/downloads/脑力奥秘" --write-url-prefix "https://oss.jnao.com/daka/brain_power"

Output: docs/data/xet_brain_power_catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "xet_brain_power_catalog.json"

TALENT_MAP = {
    "思者": {"code": 2, "tag": "思"},
    "学者": {"code": 1, "tag": "学"},
    "赢者": {"code": 5, "tag": "赢"},
    "行者": {"code": 3, "tag": "行"},
    "德者": {"code": 4, "tag": "德"},
}

# 影像记忆 / 影像追忆 视为同一技能
SKILL_ALIASES = {
    "影像追忆": "影像追忆",
    "影像记忆": "影像追忆",
    "扫描速记": "扫描速记",
    "极速学习": "极速学习",
    "极速运算": "极速运算",
}

FILENAME_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)"
    r"(?P<skill>影像追忆|影像记忆|扫描速记|极速学习|极速运算)"
    r"(?P<stage>\d+)阶段(?P<part>\d+)"
    r"\.mp3$",
    re.IGNORECASE,
)
ENERGY_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)精力恢复\.mp3$",
    re.IGNORECASE,
)


def parse_file(path: Path) -> dict | None:
    m = FILENAME_RE.match(path.name)
    if m:
        talent_name = m.group("talent")
        skill_raw = m.group("skill")
        skill = SKILL_ALIASES.get(skill_raw, skill_raw)
        talent = TALENT_MAP[talent_name]
        stage = int(m.group("stage"))
        part = int(m.group("part"))
    else:
        m2 = ENERGY_RE.match(path.name)
        if not m2:
            return None
        talent_name = m2.group("talent")
        skill_raw = "精力恢复"
        skill = "精力恢复"
        talent = TALENT_MAP[talent_name]
        stage = 0
        part = 1

    return {
        "file_name": path.name,
        "local_path": str(path.resolve()),
        "file_size_bytes": path.stat().st_size,
        "talent_name": talent_name,
        "talent_code": talent["code"],
        "talent_tag": talent["tag"],
        "skill": skill,
        "skill_raw": skill_raw,
        "stage": stage,
        "part": part,
        "lesson_sort": stage * 10 + part,
        "play_url": None,
    }


def sort_key(item: dict) -> tuple:
    return (
        item["talent_code"],
        item["skill"],
        item["stage"],
        item["part"],
        item["file_name"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan 脑力奥秘 MP3 folder -> catalog JSON")
    parser.add_argument("source_dir", help="Root folder containing downloaded MP3s (recursive)")
    parser.add_argument(
        "--write-url-prefix",
        help="If set, play_url = prefix/talent_tag/skill/stage/part.mp3 (lowercase ascii path)",
    )
    args = parser.parse_args()

    source = Path(args.source_dir)
    if not source.is_dir():
        raise SystemExit(f"Not a directory: {source}")

    items: list[dict] = []
    skipped: list[str] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".mp3":
            continue
        row = parse_file(path)
        if row is None:
            skipped.append(path.name)
            continue
        if args.write_url_prefix:
            prefix = args.write_url_prefix.rstrip("/")
            skill_slug = {
                "影像追忆": "yingxiangzhuiyi",
                "扫描速记": "saomiaosuji",
                "极速学习": "jisuxuexi",
                "极速运算": "jisuyunsuan",
                "精力恢复": "jinglihuifu",
            }[row["skill"]]
            tag_slug = {"思": "si", "学": "xue", "赢": "ying", "行": "xing", "德": "de"}[row["talent_tag"]]
            row["play_url"] = f"{prefix}/{tag_slug}/{skill_slug}/{row['stage']}_{row['part']}.mp3"
        items.append(row)

    items.sort(key=sort_key)
    counts_talent = dict(Counter(i["talent_tag"] for i in items))
    counts_skill = dict(Counter(i["skill"] for i in items))

    payload = {
        "source": "xiaoetong_local_download",
        "source_folder": str(source.resolve()),
        "series": "脑力奥秘",
        "total": len(items),
        "skipped_files": skipped,
        "counts_by_talent_tag": counts_talent,
        "counts_by_skill": counts_skill,
        "items": items,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scanned: {source}")
    print(f"Matched MP3: {len(items)}")
    print(f"Skipped (name not parsed): {len(skipped)}")
    if skipped:
        print("Skipped examples:", skipped[:10])
    print(f"By talent: {counts_talent}")
    print(f"By skill: {counts_skill}")
    print(f"Wrote -> {OUT}")


if __name__ == "__main__":
    main()
