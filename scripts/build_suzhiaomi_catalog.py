"""从 OSS 索引生成「素质奥秘 suzhiaomi」catalog — 含超脑速读→超脑阅读映射。

用法:
  python scripts/build_suzhiaomi_catalog.py
  python scripts/build_suzhiaomi_catalog.py --from-oss-index docs/data/oss_yinpin_index.json

输出: docs/data/xet_suzhiaomi_catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "xet_suzhiaomi_catalog.json"
DEFAULT_OSS_INDEX = ROOT / "docs" / "data" / "oss_yinpin_index.json"

TALENT_MAP = {
    "思者": {"code": 2, "tag": "思"},
    "学者": {"code": 1, "tag": "学"},
    "赢者": {"code": 5, "tag": "赢"},
    "行者": {"code": 3, "tag": "行"},
    "德者": {"code": 4, "tag": "德"},
}

# OSS 文件名技能 → 系统标准技能名
SKILL_CANONICAL = {
    "超脑速读": "超脑阅读",
    "绘画灵感": "天赋绘画",
    "音乐灵感": "音乐灵感",
    "我是冠军": "我是冠军",
    "棋类专注": "棋类专注",
    "考前减压": "考前减压",
}

STAGED_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)"
    r"(?P<skill>绘画灵感|音乐灵感)"
    r"(?P<stage>\d+)阶段(?P<part>\d+)"
    r"\.mp3$",
    re.IGNORECASE,
)
SINGLE_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)"
    r"(?P<skill>超脑速读|我是冠军|棋类专注|考前减压)"
    r"\.mp3$",
    re.IGNORECASE,
)


def parse_file_name(name: str, *, size: int = 0) -> dict | None:
    m = STAGED_RE.match(name)
    if m:
        talent_name = m.group("talent")
        skill_raw = m.group("skill")
        talent = TALENT_MAP[talent_name]
        stage = int(m.group("stage"))
        part = int(m.group("part"))
    else:
        m2 = SINGLE_RE.match(name)
        if not m2:
            return None
        talent_name = m2.group("talent")
        skill_raw = m2.group("skill")
        talent = TALENT_MAP[talent_name]
        # 无阶段文件：超脑阅读首日 = 1阶段1；其余单课 stage=0
        if skill_raw == "超脑速读":
            stage, part = 1, 1
        else:
            stage, part = 0, 1

    skill = SKILL_CANONICAL.get(skill_raw, skill_raw)
    if skill_raw == "超脑速读":
        lesson_sort = 11
    elif stage:
        lesson_sort = stage * 10 + part
    else:
        single_order = {"棋类专注": 50, "我是冠军": 51, "考前减压": 52}
        lesson_sort = single_order.get(skill_raw, 80)

    return {
        "file_name": name,
        "file_size_bytes": size,
        "talent_name": talent_name,
        "talent_code": talent["code"],
        "talent_tag": talent["tag"],
        "skill": skill,
        "skill_raw": skill_raw,
        "stage": stage,
        "part": part,
        "lesson_sort": lesson_sort,
        "series": "suzhiaomi",
        "play_url": None,
        "oss_key": None,
    }


def sort_key(item: dict) -> tuple:
    order = {"超脑阅读": 1, "天赋绘画": 2, "音乐灵感": 3, "棋类专注": 4, "我是冠军": 5, "考前减压": 6}
    return (
        item["talent_code"],
        order.get(item["skill"], 9),
        item["stage"],
        item["part"],
        item["file_name"],
    )


def from_oss_index(index_path: Path) -> tuple[list[dict], list[str]]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    items: list[dict] = []
    skipped: list[str] = []
    for row in data.get("items", []):
        key = row.get("key", "")
        if "/suzhiaomi/" not in key:
            continue
        name = row.get("file_name") or key.rsplit("/", 1)[-1]
        parsed = parse_file_name(name, size=int(row.get("size") or 0))
        if not parsed:
            skipped.append(name)
            continue
        parsed["play_url"] = row.get("url")
        parsed["oss_key"] = key
        items.append(parsed)
    items.sort(key=sort_key)
    return items, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="OSS suzhiaomi → catalog JSON")
    parser.add_argument(
        "--from-oss-index",
        default=str(DEFAULT_OSS_INDEX),
        help="OSS 索引 JSON（默认 docs/data/oss_yinpin_index.json）",
    )
    args = parser.parse_args()

    index_path = Path(args.from_oss_index)
    items, skipped = from_oss_index(index_path)
    counts_talent = dict(Counter(i["talent_tag"] for i in items))
    counts_skill = dict(Counter(i["skill"] for i in items))

    payload = {
        "source": "oss_index",
        "source_index": str(index_path.resolve()),
        "series": "素质奥秘",
        "series_code": "suzhiaomi",
        "total": len(items),
        "skipped_files": skipped,
        "counts_by_talent_tag": counts_talent,
        "counts_by_skill": counts_skill,
        "skill_oss_to_canonical": SKILL_CANONICAL,
        "items": items,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"From: {index_path}")
    print(f"Matched: {len(items)}, skipped: {len(skipped)}")
    if skipped:
        print("Skipped:", skipped[:5])
    print(f"By talent: {counts_talent}")
    print(f"By skill: {counts_skill}")
    print(f"Wrote -> {OUT}")


if __name__ == "__main__":
    main()
