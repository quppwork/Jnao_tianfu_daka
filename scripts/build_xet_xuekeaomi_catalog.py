"""从 OSS 索引或本地 MP3 生成「学科奥秘」catalog JSON。

用法:
  python scripts/build_xet_xuekeaomi_catalog.py
  python scripts/build_xet_xuekeaomi_catalog.py --from-oss-index docs/data/oss_yinpin_index.json
  python scripts/build_xet_xuekeaomi_catalog.py "D:/downloads/学科奥秘"

输出: docs/data/xet_xuekeaomi_catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "xet_xuekeaomi_catalog.json"
DEFAULT_OSS_INDEX = ROOT / "docs" / "data" / "oss_yinpin_index.json"

TALENT_MAP = {
    "思者": {"code": 2, "tag": "思"},
    "学者": {"code": 1, "tag": "学"},
    "赢者": {"code": 5, "tag": "赢"},
    "行者": {"code": 3, "tag": "行"},
    "德者": {"code": 4, "tag": "德"},
}

TAG_SLUG = {"思": "si", "学": "xue", "赢": "ying", "行": "xing", "德": "de"}

FILENAME_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)"
    r"(?P<skill>数学奥秘|文科奥秘|理科奥秘|英语奥秘)"
    r"(?P<stage>\d+)阶段(?P<part>\d+)"
    r"\.mp3$",
    re.IGNORECASE,
)
ENERGY_RE = re.compile(
    r"^(?P<talent>思者|学者|赢者|行者|德者)(?:精力恢复|高效作业)\.mp3$",
    re.IGNORECASE,
)


def parse_file_name(name: str, *, size: int = 0) -> dict | None:
    m = FILENAME_RE.match(name)
    if m:
        talent_name = m.group("talent")
        skill = m.group("skill")
        talent = TALENT_MAP[talent_name]
        stage = int(m.group("stage"))
        part = int(m.group("part"))
    else:
        m2 = ENERGY_RE.match(name)
        if not m2:
            return None
        talent_name = m2.group("talent")
        skill = "高效作业" if "高效作业" in name else "精力恢复"
        talent = TALENT_MAP[talent_name]
        stage = 0
        part = 1

    return {
        "file_name": name if name.endswith(".MP3") or name.endswith(".mp3") else name,
        "file_size_bytes": size,
        "talent_name": talent_name,
        "talent_code": talent["code"],
        "talent_tag": talent["tag"],
        "skill": skill,
        "skill_raw": skill,
        "stage": stage,
        "part": part,
        "lesson_sort": stage * 10 + part,
        "series": "xuekeaomi",
        "play_url": None,
        "oss_key": None,
    }


def sort_key(item: dict) -> tuple:
    skill_order = {"数学奥秘": 1, "文科奥秘": 2, "理科奥秘": 3, "英语奥秘": 4, "高效作业": 8, "精力恢复": 9}
    return (
        item["talent_code"],
        skill_order.get(item["skill"], 5),
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
        if "/xuekeaomi/" not in key:
            continue
        name = row.get("file_name") or key.rsplit("/", 1)[-1]
        parsed = parse_file_name(name, size=int(row.get("size") or 0))
        if not parsed:
            skipped.append(name)
            continue
        parsed["file_name"] = name
        parsed["play_url"] = row.get("url")
        parsed["oss_key"] = key
        items.append(parsed)
    items.sort(key=sort_key)
    return items, skipped


def from_local_dir(source: Path) -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    skipped: list[str] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".mp3":
            continue
        parsed = parse_file_name(path.name, size=path.stat().st_size)
        if not parsed:
            skipped.append(path.name)
            continue
        parsed["file_name"] = path.name
        parsed["local_path"] = str(path.resolve())
        tag_slug = TAG_SLUG[parsed["talent_tag"]]
        parsed["oss_key"] = f"yinpin/xuekeaomi/{tag_slug}/{path.name}"
        items.append(parsed)
    items.sort(key=sort_key)
    return items, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="生成学科奥秘 catalog JSON")
    parser.add_argument("source_dir", nargs="?", help="本地 MP3 根目录（可选）")
    parser.add_argument(
        "--from-oss-index",
        default=str(DEFAULT_OSS_INDEX),
        help="从 oss_yinpin_index.json 读取 xuekeaomi 条目",
    )
    args = parser.parse_args()

    if args.source_dir:
        items, skipped = from_local_dir(Path(args.source_dir))
        source_label = str(Path(args.source_dir).resolve())
    else:
        index_path = Path(args.from_oss_index)
        if not index_path.exists():
            raise SystemExit(f"OSS 索引不存在: {index_path}，请先运行 scripts/oss_audio.py list")
        items, skipped = from_oss_index(index_path)
        source_label = str(index_path.resolve())

    counts_talent = dict(Counter(i["talent_tag"] for i in items))
    counts_skill = dict(Counter(i["skill"] for i in items))

    payload = {
        "source": "xiaoetong_local_download",
        "source_folder": source_label,
        "series": "学科奥秘",
        "series_code": "xuekeaomi",
        "total": len(items),
        "skipped_files": skipped,
        "counts_by_talent_tag": counts_talent,
        "counts_by_skill": counts_skill,
        "items": items,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"来源: {source_label}")
    print(f"匹配 MP3: {len(items)}")
    print(f"跳过: {len(skipped)}")
    if skipped:
        print("跳过示例:", skipped[:10])
    print(f"天赋分布: {counts_talent}")
    print(f"学科分布: {counts_skill}")
    print(f"写入 -> {OUT}")


if __name__ == "__main__":
    main()
