"""OSS 音频/视频工具 — 列举、匹配目录、写入 play_url、导入数据库

用法（在项目根目录）:
  pip install oss2
  # 先在 backend/.env 配置 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET

  python scripts/oss_audio.py list
  python scripts/oss_audio.py list-videos
  python scripts/oss_audio.py sync-catalog
  python scripts/oss_audio.py sync-videos
  python scripts/oss_audio.py build-xue-catalog
  python scripts/oss_audio.py import-db --all
  python scripts/oss_audio.py import-db --replace
  python scripts/oss_audio.py import-videos
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=True)

DEFAULT_CATALOG = ROOT / "docs" / "data" / "xet_brain_power_catalog.json"
XUE_CATALOG = ROOT / "docs" / "data" / "xet_xuekeaomi_catalog.json"
VIDEO_CATALOG = ROOT / "docs" / "data" / "xet_video_catalog.json"
OSS_INDEX = ROOT / "docs" / "data" / "oss_yinpin_index.json"
VIDEO_PREFIX = "shipin/"


def _series_from_prefix(prefix: str | None) -> str:
    p = (prefix or "yinpin/").lower()
    if "xuekeaomi" in p:
        return "xuekeaomi"
    if "chaonengli" in p:
        return "chaonengli"
    if "zhuanzhuli" in p:
        return "zhuanzhuli"
    return "chaonaoaomi"


def _norm_name(name: str) -> str:
    return Path(name).name.lower()


def cmd_list(args: argparse.Namespace) -> None:
    from app.services.oss_client import list_audio_objects

    items = list_audio_objects(args.prefix)
    print(f"OSS MP3 共 {len(items)} 个（prefix={args.prefix or 'yinpin/'}）")
    for row in items[:20]:
        print(f"  {row['file_name']}  ({row['size'] // 1024} KB)")
    if len(items) > 20:
        print(f"  ... 还有 {len(items) - 20} 个")
    if args.out:
        payload = {"total": len(items), "items": items}
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {args.out}")


def cmd_sync_catalog(args: argparse.Namespace) -> None:
    from app.services.oss_client import list_audio_objects, public_url

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        raise SystemExit(f"目录不存在: {catalog_path}")

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    oss_items = list_audio_objects(args.prefix)
    by_name = {_norm_name(o["file_name"]): o for o in oss_items}

    matched = 0
    missing: list[str] = []
    for row in data.get("items", []):
        fname = row.get("file_name", "")
        hit = by_name.get(_norm_name(fname))
        if hit:
            row["play_url"] = hit["url"] if not args.public_prefix else f"{args.public_prefix.rstrip('/')}/{hit['key'].split('/', 1)[-1]}"
            row["oss_key"] = hit["key"]
            row["series"] = row.get("series") or _series_from_prefix(args.prefix)
            matched += 1
        else:
            missing.append(fname)

    catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    OSS_INDEX.write_text(
        json.dumps({"total": len(oss_items), "items": oss_items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"目录: {catalog_path}")
    print(f"OSS 文件: {len(oss_items)}，匹配成功: {matched}/{len(data.get('items', []))}")
    if missing:
        print(f"未匹配 {len(missing)} 个，示例: {missing[:5]}")


def cmd_build_xue(args: argparse.Namespace) -> None:
    import subprocess

    cmd = [sys.executable, str(ROOT / "scripts" / "build_xet_xuekeaomi_catalog.py")]
    if args.oss_index:
        cmd.extend(["--from-oss-index", args.oss_index])
    if args.source_dir:
        cmd.append(args.source_dir)
    subprocess.check_call(cmd)


def cmd_list_videos(args: argparse.Namespace) -> None:
    from app.services.oss_client import list_video_objects

    prefix = args.prefix or VIDEO_PREFIX
    items = list_video_objects(prefix)
    print(f"OSS 视频共 {len(items)} 个（prefix={prefix}）")
    for row in items:
        print(f"  {row['key']}  ({row['size'] // (1024 * 1024)} MB)")
    if args.out:
        payload = {"total": len(items), "prefix": prefix, "items": items}
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {args.out}")


def _video_skill_from_name(file_name: str) -> str:
    from app.services.content_meta import skill_from_title

    return skill_from_title(file_name)


def cmd_sync_videos(args: argparse.Namespace) -> None:
    from app.services.oss_client import list_video_objects

    prefix = args.prefix or VIDEO_PREFIX
    catalog_path = Path(args.catalog)
    oss_items = list_video_objects(prefix)
    by_key = {o["key"]: o for o in oss_items}

    if catalog_path.exists():
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        items = data.get("items", [])
    else:
        data = {"source": "oss_shipin", "series_code": "shipin", "items": []}
        items = []

    matched = 0
    missing: list[str] = []
    for row in items:
        key = row.get("oss_key", "")
        hit = by_key.get(key)
        if hit:
            row["play_url"] = hit["url"]
            row["file_size_bytes"] = hit["size"]
            matched += 1
        else:
            missing.append(key or row.get("file_name", "?"))

    if args.refresh and oss_items:
        existing_keys = {row.get("oss_key") for row in items}
        next_id = max((row.get("id") or 0 for row in items), default=0) + 1
        for hit in oss_items:
            if hit["key"] in existing_keys:
                continue
            fname = hit["file_name"]
            skill = _video_skill_from_name(fname)
            items.append({
                "id": next_id,
                "file_name": fname,
                "oss_key": hit["key"],
                "play_url": hit["url"],
                "lesson_title": Path(fname).stem.lstrip("_").lstrip("0123456789."),
                "skill": skill,
                "talent_code": 0,
                "talent_tag": "?",
                "lesson_sort": 1,
                "series": "shipin",
                "file_size_bytes": hit["size"],
            })
            next_id += 1
            matched += 1

    data["items"] = items
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"目录: {catalog_path}")
    print(f"OSS 视频: {len(oss_items)}，已同步: {matched}/{len(items)}")
    if missing:
        print(f"目录中未在 OSS 找到 {len(missing)} 个: {missing[:5]}")


def cmd_import_videos(args: argparse.Namespace) -> None:
    from app.db.session import get_session_factory, init_db
    from app.services.catalog_import import import_video_catalog

    init_db()
    session = get_session_factory()()
    try:
        n = import_video_catalog(session, Path(args.catalog), replace=args.replace)
        print(f"导入/更新 {n} 条视频 content_item（replace={args.replace}）")
    finally:
        session.close()


def cmd_import_db(args: argparse.Namespace) -> None:
    from app.db.session import get_session_factory, init_db
    from app.services.catalog_import import import_all_xet_catalogs, import_catalog

    init_db()
    session = get_session_factory()()
    try:
        if args.all:
            results = import_all_xet_catalogs(session, replace=args.replace)
            for name, n in results.items():
                print(f"  {name}: {n} 条")
            print(f"合计导入/更新 {sum(results.values())} 条 content_item")
        else:
            n = import_catalog(session, Path(args.catalog), replace=args.replace)
            print(f"导入/更新 {n} 条 content_item（replace={args.replace}）")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="阿里云 OSS 音频同步工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列举 OSS yinpin/ 下 MP3")
    p_list.add_argument("--prefix", default=None, help="OSS 前缀，默认 yinpin/")
    p_list.add_argument("--out", help="导出 JSON 路径")
    p_list.set_defaults(func=cmd_list)

    p_vlist = sub.add_parser("list-videos", help="列举 OSS shipin/ 下视频")
    p_vlist.add_argument("--prefix", default=None, help="OSS 前缀，默认 shipin/")
    p_vlist.add_argument("--out", help="导出 JSON 路径")
    p_vlist.set_defaults(func=cmd_list_videos)

    p_sync = sub.add_parser("sync-catalog", help="按文件名匹配 OSS → 更新 catalog play_url")
    p_sync.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p_sync.add_argument("--prefix", default=None)
    p_sync.add_argument(
        "--public-prefix",
        help="若 Bucket 已设公开读，可指定 CDN/自定义域名前缀覆盖 URL",
    )
    p_sync.set_defaults(func=cmd_sync_catalog)

    p_vsync = sub.add_parser("sync-videos", help="同步 OSS shipin/ → 视频 catalog play_url")
    p_vsync.add_argument("--catalog", default=str(VIDEO_CATALOG))
    p_vsync.add_argument("--prefix", default=None)
    p_vsync.add_argument(
        "--refresh",
        action="store_true",
        help="将 OSS 新增视频追加进 catalog JSON",
    )
    p_vsync.set_defaults(func=cmd_sync_videos)

    p_db = sub.add_parser("import-db", help="将 catalog JSON 导入 MySQL content_item")
    p_db.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p_db.add_argument("--replace", action="store_true", help="清空后重新导入（--all 时仅首份 catalog 清空）")
    p_db.add_argument("--all", action="store_true", help="导入脑力奥秘 + 学科奥秘两份 catalog")
    p_db.set_defaults(func=cmd_import_db)

    p_vdb = sub.add_parser("import-videos", help="将视频 catalog 导入 MySQL content_item")
    p_vdb.add_argument("--catalog", default=str(VIDEO_CATALOG))
    p_vdb.add_argument("--replace", action="store_true", help="清空已有视频后重新导入")
    p_vdb.set_defaults(func=cmd_import_videos)

    p_xue = sub.add_parser("build-xue-catalog", help="从 OSS 索引生成学科奥秘 catalog")
    p_xue.add_argument("--oss-index", default=str(OSS_INDEX))
    p_xue.add_argument("source_dir", nargs="?", help="可选：本地 MP3 目录")
    p_xue.set_defaults(func=cmd_build_xue)

    args = parser.parse_args()
    if not os.getenv("OSS_ACCESS_KEY_ID") or not os.getenv("OSS_ACCESS_KEY_SECRET"):
        print("请先在 backend/.env 配置:")
        print("  OSS_ACCESS_KEY_ID=你的AccessKey")
        print("  OSS_ACCESS_KEY_SECRET=你的AccessKeySecret")
        print("  OSS_BUCKET=jnao-talent-ai")
        print("  OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com")
        print("  OSS_PREFIX=yinpin/")
        raise SystemExit(1)
    args.func(args)


if __name__ == "__main__":
    main()
