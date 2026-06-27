"""音频目录 JSON → content_item"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.talent_mapping import EXPECTED_COUNTS_BY_TAG
from app.db.models import ContentItem
from app.services.content_meta import build_instructions_meta

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = PROJECT_ROOT / "docs" / "data" / "xet_brain_power_catalog.json"


def catalog_path() -> Path:
    return DEFAULT_CATALOG


def load_catalog_data(path: Path | None = None) -> dict:
    p = path or catalog_path()
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def import_catalog(db: Session, path: Path | None = None, replace: bool = False) -> int:
    data = load_catalog_data(path)
    if data.get("source") == "xiaoetong_local_download":
        return import_xet_catalog(db, data, replace=replace)
    items = data.get("items", [])
    if replace:
        db.query(ContentItem).delete()
    existing = {sid for sid in db.scalars(select(ContentItem.source_id)).all() if sid is not None}
    inserted = 0
    for row in items:
        source_id = row.get("id")
        if source_id in existing:
            continue
        db.add(
            ContentItem(
                source_id=source_id,
                course_id=row.get("course_id"),
                talent_code=row["talent_code"],
                talent_tag=row.get("talent_tag"),
                lesson_title=row.get("lesson_title"),
                lesson_sort=row.get("lesson_sort", 0),
                play_url=row["play_url"],
                content_type="audio",
                instructions=build_instructions_meta(row, play_url=row["play_url"]),
                status=1,
            )
        )
        inserted += 1
    db.commit()
    return inserted


def validate_catalog_counts(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in db.scalars(select(ContentItem)).all():
        tag = item.talent_tag or "?"
        counts[tag] = counts.get(tag, 0) + 1
    return counts


def counts_match_expected(db: Session) -> bool:
    counts = validate_catalog_counts(db)
    return counts == EXPECTED_COUNTS_BY_TAG


def _lesson_title_from_xet(row: dict) -> str:
    if row.get("lesson_title"):
        return row["lesson_title"]
    name = row.get("file_name", "")
    if name:
        return Path(name).stem
    skill = row.get("skill", "")
    stage = row.get("stage", 0)
    part = row.get("part", 0)
    if skill in ("精力恢复", "高效作业"):
        return f"{row.get('talent_name', '')}{skill}"
    if skill == "感知力" or row.get("skill_raw") == "多元感知":
        return f"{row.get('talent_name', '')}多元感知"
    return f"{row.get('talent_name', '')}{skill}{stage}阶段{part}"


def import_xet_catalog(db: Session, data: dict, *, replace: bool = False) -> int:
    """小鹅通目录 → content_item（支持 chaonaoaomi / xuekeaomi）"""
    items = data.get("items", [])
    series_code = data.get("series_code") or "chaonaoaomi"
    if replace:
        db.query(ContentItem).delete()
        existing: set[str] = set()
    else:
        existing = {
            f"{parse_series_from_item(r)}:{r.talent_code}:{r.lesson_sort}:{r.lesson_title}"
            for r in db.scalars(select(ContentItem)).all()
        }
    inserted = 0
    updated = 0
    for idx, row in enumerate(items, start=1):
        if not row.get("play_url"):
            continue
        row_series = row.get("series") or series_code
        row = {**row, "series": row_series}
        title = _lesson_title_from_xet(row)
        key = f"{row_series}:{row['talent_code']}:{row.get('lesson_sort', 0)}:{title}"
        if key in existing:
            if replace:
                continue
            item = db.scalar(
                select(ContentItem).where(
                    ContentItem.talent_code == row["talent_code"],
                    ContentItem.lesson_sort == row.get("lesson_sort", 0),
                    ContentItem.lesson_title == title,
                )
            )
            if item and item.play_url != row["play_url"]:
                item.play_url = row["play_url"]
                item.instructions = build_instructions_meta(row, play_url=row["play_url"])
                updated += 1
            continue
        db.add(
            ContentItem(
                source_id=idx,
                talent_code=row["talent_code"],
                talent_tag=row.get("talent_tag"),
                lesson_title=title,
                lesson_sort=row.get("lesson_sort", 0),
                play_url=row["play_url"],
                content_type="audio",
                instructions=build_instructions_meta(row, play_url=row["play_url"]),
                status=1,
            )
        )
        inserted += 1
    db.commit()
    return inserted + updated


def parse_series_from_item(item: ContentItem) -> str:
    from app.services.content_meta import parse_item_meta

    return parse_item_meta(item).get("series") or "chaonaoaomi"


def import_all_xet_catalogs(db: Session, *, replace: bool = False) -> dict[str, int]:
    """导入脑力奥秘 + 学科奥秘两份 catalog"""
    paths = [
        PROJECT_ROOT / "docs" / "data" / "xet_brain_power_catalog.json",
        PROJECT_ROOT / "docs" / "data" / "xet_xuekeaomi_catalog.json",
        PROJECT_ROOT / "docs" / "data" / "xet_suzhiaomi_catalog.json",
        PROJECT_ROOT / "docs" / "data" / "xet_duoyuanganzhi_catalog.json",
    ]
    results: dict[str, int] = {}
    for i, path in enumerate(paths):
        if not path.exists():
            results[path.name] = 0
            continue
        results[path.name] = import_catalog(
            db, path, replace=replace and i == 0,
        )
    return results
