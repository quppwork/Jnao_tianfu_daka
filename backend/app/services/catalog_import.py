"""音频/视频目录 → content_item（JSON catalog + OSS 直扫）"""

import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.talent_mapping import EXPECTED_COUNTS_BY_TAG
from app.db.models import ContentItem
from app.services.content_meta import build_instructions_meta, parse_item_meta


def catalog_data_dir() -> Path:
    """catalog JSON 目录：本地=项目 docs/data；Docker=CATALOG_DATA_DIR 或 /catalog_data"""
    env = os.getenv("CATALOG_DATA_DIR", "").strip()
    if env:
        return Path(env)
    backend_root = Path(__file__).resolve().parents[2]
    monorepo = backend_root.parent
    if (monorepo / "docs" / "data").is_dir():
        return monorepo / "docs" / "data"
    docker_fallback = Path("/catalog_data")
    if docker_fallback.is_dir():
        return docker_fallback
    return monorepo / "docs" / "data"


DEFAULT_CATALOG = catalog_data_dir() / "xet_brain_power_catalog.json"


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
    """导入脑力奥秘 + 学科奥秘等 catalog"""
    base = catalog_data_dir()
    paths = [
        base / "xet_brain_power_catalog.json",
        base / "xet_xuekeaomi_catalog.json",
        base / "xet_suzhiaomi_catalog.json",
        base / "xet_duoyuanganzhi_catalog.json",
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


def _content_item_by_oss_key(db: Session, oss_key: str) -> ContentItem | None:
    """按 instructions 中的 oss_key 查找已有 content_item"""
    for row in db.scalars(select(ContentItem)).all():
        meta = parse_item_meta(row)
        if meta.get("oss_key") == oss_key:
            return row
    return None


def _content_item_by_video_identity(
    db: Session,
    *,
    skill: str | None,
    file_name: str | None,
) -> ContentItem | None:
    """按技能或文件名匹配已有视频（OSS 路径变更时仍能更新而非重复插入）"""
    from app.services.content_meta import parse_item_meta, skill_from_title

    skill = (skill or "").strip()
    file_name = (file_name or "").strip()
    if not skill and not file_name:
        return None
    for row in db.scalars(select(ContentItem).where(ContentItem.content_type == "video")):
        meta = parse_item_meta(row)
        row_skill = (meta.get("skill") or skill_from_title(row.lesson_title) or "").strip()
        if skill and row_skill == skill:
            return row
        old_key = str(meta.get("oss_key") or "")
        play_url = row.play_url or ""
        if file_name and (
            old_key.endswith(file_name)
            or file_name in play_url
            or file_name.replace(".mp4", "") in (row.lesson_title or "")
        ):
            return row
    return None


def repair_video_oss_paths(db: Session) -> dict:
    """视频从 shipin/天赋-视频/ 挪到 shipin/ 根目录后，刷新 DB 里残留的旧 URL"""
    from app.db.models import TrainingItem

    content_updated = 0
    training_updated = 0
    old_segment = "shipin/天赋-视频/"

    for row in db.scalars(select(ContentItem).where(ContentItem.content_type == "video")):
        row_changed = False
        for field in ("play_url", "video_url"):
            url = getattr(row, field) or ""
            if old_segment not in url:
                continue
            setattr(row, field, url.replace(old_segment, "shipin/"))
            row_changed = True
        if row_changed:
            try:
                meta = parse_item_meta(row)
                if isinstance(meta, dict) and old_segment in str(meta.get("oss_key") or ""):
                    meta["oss_key"] = str(meta["oss_key"]).replace(old_segment, "shipin/")
                    row.instructions = json.dumps(meta, ensure_ascii=False)
            except Exception:
                pass
            content_updated += 1

    for item in db.scalars(select(TrainingItem).where(TrainingItem.video_url.isnot(None))):
        url = item.video_url or ""
        if old_segment not in url:
            continue
        item.video_url = url.replace(old_segment, "shipin/")
        training_updated += 1

    if content_updated or training_updated:
        db.commit()
    return {"content_items": content_updated, "training_items": training_updated}


def import_video_catalog(db: Session, path: Path | None = None, *, replace: bool = False) -> int:
    """OSS 视频目录 → content_item（开口窍/极速运算/五者天赋等）"""
    p = path or (catalog_data_dir() / "xet_video_catalog.json")
    if not p.exists():
        return 0
    data = load_catalog_data(p)
    items = data.get("items", [])
    if replace:
        db.query(ContentItem).filter(ContentItem.content_type == "video").delete()
    inserted = 0
    updated = 0
    for row in items:
        if not row.get("play_url"):
            continue
        oss_key = row.get("oss_key") or ""
        title = row.get("lesson_title") or row.get("file_name", "")
        instructions = build_instructions_meta(row, play_url=row["play_url"])
        existing = _content_item_by_oss_key(db, oss_key) if oss_key else None
        if not existing and row.get("play_url"):
            existing = db.scalar(
                select(ContentItem).where(ContentItem.play_url == row["play_url"])
            )
        if not existing:
            existing = _content_item_by_video_identity(
                db,
                skill=row.get("skill"),
                file_name=row.get("file_name"),
            )
        if existing:
            changed = False
            if existing.play_url != row["play_url"]:
                existing.play_url = row["play_url"]
                changed = True
            if existing.video_url != row["play_url"]:
                existing.video_url = row["play_url"]
                changed = True
            if existing.lesson_title != title:
                existing.lesson_title = title
                changed = True
            if existing.instructions != instructions:
                existing.instructions = instructions
                changed = True
            if existing.content_type != "video":
                existing.content_type = "video"
                changed = True
            if changed:
                updated += 1
            continue
        db.add(
            ContentItem(
                source_id=row.get("id"),
                talent_code=row.get("talent_code", 0),
                talent_tag=row.get("talent_tag"),
                lesson_title=title,
                lesson_sort=row.get("lesson_sort", 0),
                play_url=row["play_url"],
                video_url=row["play_url"],
                content_type="video",
                instructions=instructions,
                status=1,
            )
        )
        inserted += 1
    db.commit()
    return inserted + updated


# ═══════════════════════════════════════════════════════════════
# OSS 直扫导入（无需 JSON catalog，直接从 OSS 列举 + 入库）
# ═══════════════════════════════════════════════════════════════

def import_from_oss(
    db: Session,
    *,
    prefix: str | None = None,
    media_type: str = "all",
    talent_tag_map: dict[str, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """扫描 OSS 目录，将新媒体文件导入 content_item。

    Args:
        db: 数据库会话
        prefix: OSS 扫描前缀（默认取配置的 yinpin/）
        media_type: "audio" | "video" | "all"
        talent_tag_map: 文件名关键词 → 天赋标签映射
        dry_run: True = 只返回扫描结果，不写入数据库

    Returns:
        {scanned: int, new_audio: int, new_video: int, skipped: int, items: [...]}
    """
    from app.services.oss_client import (
        _oss_cfg,
        _list_objects,
        is_oss_configured,
    )

    if not is_oss_configured():
        return {"error": "OSS 未配置", "scanned": 0, "new_audio": 0,
                "new_video": 0, "skipped": 0, "items": []}

    cfg = _oss_cfg()
    use_prefix = prefix or cfg["prefix"]

    # 扫描 OSS
    objects = _list_objects(use_prefix, media_type)  # type: ignore[arg-type]
    if not objects:
        return {"scanned": 0, "new_audio": 0, "new_video": 0,
                "skipped": 0, "items": []}

    # 现有 URL → ContentItem 映射（去重）
    existing_urls: set[str] = {
        url for url in
        db.scalars(select(ContentItem.play_url)).all()
        if url
    }

    # 天赋标签映射（文件名关键词 → talent_code, talent_tag）
    if talent_tag_map is None:
        talent_tag_map = _default_talent_tag_map()

    new_audio = 0
    new_video = 0
    skipped = 0
    new_items: list[dict] = []

    for obj in objects:
        url = obj["url"]
        if url in existing_urls:
            skipped += 1
            continue

        file_name = obj["file_name"]
        content_type = obj["media_type"]
        talent_code, talent_tag = _guess_talent(file_name, talent_tag_map)

        # 解析技能/阶段元数据
        meta = _parse_oss_file_name(file_name)
        instructions = json.dumps(meta, ensure_ascii=False)

        if not dry_run:
            db.add(ContentItem(
                talent_code=talent_code,
                talent_tag=talent_tag,
                lesson_title=file_name,
                lesson_sort=meta.get("lesson_sort", 0),
                play_url=url,
                video_url=url if content_type == "video" else None,
                content_type=content_type,
                instructions=instructions,
                status=1,
            ))

        if content_type == "video":
            new_video += 1
        else:
            new_audio += 1

        new_items.append({
            "file_name": file_name,
            "content_type": content_type,
            "talent_code": talent_code,
            "talent_tag": talent_tag,
            "url": url,
        })

    if not dry_run and (new_audio + new_video) > 0:
        db.commit()

    return {
        "scanned": len(objects),
        "new_audio": new_audio,
        "new_video": new_video,
        "skipped": skipped,
        "items": new_items,
    }


def _default_talent_tag_map() -> dict[str, tuple[int, str]]:
    """默认天赋标签映射：文件名包含关键词 → (talent_code, talent_tag)"""
    return {
        "学者": (1, "学"),
        "学_": (1, "学"),
        "思者": (2, "思"),
        "思_": (2, "思"),
        "行者": (3, "行"),
        "行_": (3, "行"),
        "德者": (4, "德"),
        "德_": (4, "德"),
        "赢者": (5, "赢"),
        "赢_": (5, "赢"),
    }


def _guess_talent(
    file_name: str,
    tag_map: dict[str, tuple[int, str]],
) -> tuple[int, str]:
    """根据文件名猜测天赋编码和标签"""
    for keyword, (code, tag) in tag_map.items():
        if keyword in file_name:
            return code, tag
    return 0, "?"


def _parse_oss_file_name(file_name: str) -> dict:
    """从 OSS 文件名解析技能/阶段/part 等元数据"""
    from app.services.content_meta import guess_skill_stage_part

    meta = guess_skill_stage_part(file_name)
    # 判断内容类型
    ext = os.path.splitext(file_name)[1].lower()
    from app.services.oss_client import VIDEO_EXTENSIONS
    meta["content_type"] = "video" if ext in VIDEO_EXTENSIONS else "audio"
    return meta
