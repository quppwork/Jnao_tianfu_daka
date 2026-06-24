"""OSS 音频工具 — 列举、匹配目录、写入 play_url、导入数据库

用法（在项目根目录）:
  pip install oss2
  # 先在 backend/.env 配置 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET

  python scripts/oss_audio.py list
  python scripts/oss_audio.py sync-catalog
  python scripts/oss_audio.py import-db --replace
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
OSS_INDEX = ROOT / "docs" / "data" / "oss_yinpin_index.json"


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


def cmd_import_db(args: argparse.Namespace) -> None:
    from app.db.session import get_session_factory, init_db
    from app.services.catalog_import import import_catalog

    init_db()
    session = get_session_factory()()
    try:
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

    p_sync = sub.add_parser("sync-catalog", help="按文件名匹配 OSS → 更新 catalog play_url")
    p_sync.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p_sync.add_argument("--prefix", default=None)
    p_sync.add_argument(
        "--public-prefix",
        help="若 Bucket 已设公开读，可指定 CDN/自定义域名前缀覆盖 URL",
    )
    p_sync.set_defaults(func=cmd_sync_catalog)

    p_db = sub.add_parser("import-db", help="将 catalog JSON 导入 MySQL content_item")
    p_db.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p_db.add_argument("--replace", action="store_true", help="清空后重新导入")
    p_db.set_defaults(func=cmd_import_db)

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
