#!/usr/bin/env python3
"""从企业微信拉取「已服务的外部联系人」写入 db_fz_jingnao。

对应管理后台：客户联系与上下游 → 高级功能 → 已服务的外部联系人
官方接口：POST /cgi-bin/externalcontact/contact_list

用法（在 backend 或仓库根目录）:
  python backend/tools/sync_wework_served_contacts.py
  python backend/tools/sync_wework_served_contacts.py --dry-run

环境变量:
  WEWORK_CORPID / WEWORK_CORPSECRET
  LEGACY_DATABASE_URL  （目标库，建议 db_fz_jingnao）
  WEWORK_AGENTID       （可选，仅记录）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT / ".env.production", override=False)

QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"

DDL_CONTACT = """
CREATE TABLE IF NOT EXISTS qywx_served_external_contact (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  sync_batch_id VARCHAR(32) NOT NULL COMMENT '本次同步批次',
  tmp_openid VARCHAR(128) NOT NULL DEFAULT '' COMMENT '外部联系人临时ID(当轮去重)',
  external_userid VARCHAR(64) NULL COMMENT '客户 external_userid',
  is_customer TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=客户 0=其他外部联系人',
  name VARCHAR(128) NULL COMMENT '脱敏昵称(其他外部联系人)',
  follow_userid VARCHAR(64) NULL COMMENT '添加人/群主 userid',
  chat_id VARCHAR(64) NULL COMMENT '客户群 ID',
  chat_name VARCHAR(255) NULL COMMENT '外部群名',
  add_time INT UNSIGNED NULL COMMENT '首次添加/进群 Unix 时间戳',
  add_time_dt DATETIME NULL COMMENT '首次添加/进群时间',
  synced_at DATETIME NOT NULL COMMENT '写入时间',
  PRIMARY KEY (id),
  KEY idx_batch (sync_batch_id),
  KEY idx_follow (follow_userid),
  KEY idx_external (external_userid),
  KEY idx_tmp (tmp_openid),
  KEY idx_add_time (add_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信已服务的外部联系人明细';
"""

DDL_STAT = """
CREATE TABLE IF NOT EXISTS qywx_served_external_contact_stat (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  sync_batch_id VARCHAR(32) NOT NULL COMMENT '本次同步批次',
  follow_userid VARCHAR(64) NOT NULL COMMENT '员工 userid',
  contact_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '去重后外部联系人数',
  customer_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '其中客户数',
  other_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '其中其他外部联系人数',
  synced_at DATETIME NOT NULL COMMENT '写入时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_follow (sync_batch_id, follow_userid),
  KEY idx_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信已服务外部联系人-按添加人汇总';
"""


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


def _get_engine() -> Engine:
    url = _require_env("LEGACY_DATABASE_URL")
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def get_access_token(corpid: str, corpsecret: str) -> str:
    resp = requests.get(
        f"{QYAPI}/gettoken",
        params={"corpid": corpid, "corpsecret": corpsecret},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"gettoken 失败: {data}")
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"gettoken 无 access_token: {data}")
    return token


def fetch_all_contacts(access_token: str, *, limit: int = 1000) -> list[dict[str, Any]]:
    """分页拉取 contact_list，一轮内用同一 cursor 链。"""
    rows: list[dict[str, Any]] = []
    cursor = ""
    page = 0
    while True:
        page += 1
        payload: dict[str, Any] = {"limit": limit}
        if cursor:
            payload["cursor"] = cursor
        resp = requests.post(
            f"{QYAPI}/externalcontact/contact_list",
            params={"access_token": access_token},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"contact_list 失败(page={page}): {data}")
        chunk = data.get("info_list") or []
        rows.extend(chunk)
        print(f"  page {page}: +{len(chunk)} (累计 {len(rows)})")
        cursor = (data.get("next_cursor") or "").strip()
        if not cursor:
            break
        # 避免打太猛
        time.sleep(0.05)
    return rows


def _ts_to_dt(ts: Any) -> datetime | None:
    if ts is None or ts == "":
        return None
    try:
        return datetime.fromtimestamp(int(ts))
    except (TypeError, ValueError, OSError):
        return None


def ensure_tables(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(DDL_CONTACT))
        conn.execute(text(DDL_STAT))


def build_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 follow_userid 汇总；同一员工下用 tmp_openid 去重。"""
    by_user: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"all": set(), "customer": set(), "other": set()}
    )
    for row in rows:
        uid = (row.get("follow_userid") or "").strip()
        if not uid:
            continue
        key = (row.get("tmp_openid") or row.get("external_userid") or "").strip()
        if not key:
            continue
        by_user[uid]["all"].add(key)
        if row.get("is_customer"):
            by_user[uid]["customer"].add(key)
        else:
            by_user[uid]["other"].add(key)

    result = []
    for uid, sets in sorted(by_user.items(), key=lambda x: (-len(x[1]["all"]), x[0])):
        result.append(
            {
                "follow_userid": uid,
                "contact_cnt": len(sets["all"]),
                "customer_cnt": len(sets["customer"]),
                "other_cnt": len(sets["other"]),
            }
        )
    return result


def replace_batch(
    engine: Engine,
    *,
    batch_id: str,
    rows: list[dict[str, Any]],
    stats: list[dict[str, Any]],
) -> None:
    synced_at = datetime.now().replace(microsecond=0)
    insert_contact = text(
        """
        INSERT INTO qywx_served_external_contact (
          sync_batch_id, tmp_openid, external_userid, is_customer, name,
          follow_userid, chat_id, chat_name, add_time, add_time_dt, synced_at
        ) VALUES (
          :sync_batch_id, :tmp_openid, :external_userid, :is_customer, :name,
          :follow_userid, :chat_id, :chat_name, :add_time, :add_time_dt, :synced_at
        )
        """
    )
    insert_stat = text(
        """
        INSERT INTO qywx_served_external_contact_stat (
          sync_batch_id, follow_userid, contact_cnt, customer_cnt, other_cnt, synced_at
        ) VALUES (
          :sync_batch_id, :follow_userid, :contact_cnt, :customer_cnt, :other_cnt, :synced_at
        )
        """
    )

    contact_params = []
    for row in rows:
        add_time = row.get("add_time")
        try:
            add_time_int = int(add_time) if add_time is not None else None
        except (TypeError, ValueError):
            add_time_int = None
        contact_params.append(
            {
                "sync_batch_id": batch_id,
                "tmp_openid": (row.get("tmp_openid") or "")[:128],
                "external_userid": row.get("external_userid"),
                "is_customer": 1 if row.get("is_customer") else 0,
                "name": row.get("name"),
                "follow_userid": row.get("follow_userid"),
                "chat_id": row.get("chat_id"),
                "chat_name": row.get("chat_name"),
                "add_time": add_time_int,
                "add_time_dt": _ts_to_dt(add_time_int),
                "synced_at": synced_at,
            }
        )

    stat_params = [
        {
            "sync_batch_id": batch_id,
            "follow_userid": s["follow_userid"],
            "contact_cnt": s["contact_cnt"],
            "customer_cnt": s["customer_cnt"],
            "other_cnt": s["other_cnt"],
            "synced_at": synced_at,
        }
        for s in stats
    ]

    with engine.begin() as conn:
        # 全量覆盖：只保留本批次（与后台当前快照对齐）
        conn.execute(text("DELETE FROM qywx_served_external_contact"))
        conn.execute(text("DELETE FROM qywx_served_external_contact_stat"))
        if contact_params:
            conn.execute(insert_contact, contact_params)
        if stat_params:
            conn.execute(insert_stat, stat_params)


def _default_cache_path(batch_id: str) -> Path:
    out_dir = ROOT / "docs" / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"qywx_served_contacts_{batch_id}.json"


def save_cache(path: Path, *, batch_id: str, rows: list[dict[str, Any]], stats: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": batch_id,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": len(rows),
        "stat_count": len(stats),
        "rows": rows,
        "stats": stats,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"已缓存到 {path} ({path.stat().st_size // 1024} KB)")


def load_cache(path: Path) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    batch_id = str(data.get("batch_id") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    rows = list(data.get("rows") or [])
    stats = list(data.get("stats") or build_stats(rows))
    return batch_id, rows, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="同步企业微信已服务的外部联系人到 db_fz_jingnao")
    parser.add_argument("--dry-run", action="store_true", help="只拉取/读缓存，不写库")
    parser.add_argument("--limit", type=int, default=1000, help="分页 limit，默认 1000")
    parser.add_argument("--keep-old-batches", action="store_true", help="保留历史批次（默认清空后只留本次）")
    parser.add_argument("--cache", type=str, default="", help="拉取后写入该 JSON 路径；默认 docs/export/qywx_served_contacts_<batch>.json")
    parser.add_argument("--from-json", type=str, default="", help="跳过接口，从缓存 JSON 写库（适合本机拉、服务器入库）")
    args = parser.parse_args()

    agent_id = (os.getenv("WEWORK_AGENTID") or "").strip()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    if args.from_json:
        cache_path = Path(args.from_json)
        print(f"从缓存读取: {cache_path}")
        batch_id, rows, stats = load_cache(cache_path)
    else:
        corpid = _require_env("WEWORK_CORPID")
        secret = _require_env("WEWORK_CORPSECRET")
        print(f"corpid={corpid[:6]}*** agentid={agent_id or '-'} batch={batch_id}")
        print("1) gettoken ...")
        token = get_access_token(corpid, secret)
        print("2) contact_list 分页拉取 ...")
        rows = fetch_all_contacts(token, limit=args.limit)
        stats = build_stats(rows)
        cache_path = Path(args.cache) if args.cache else _default_cache_path(batch_id)
        save_cache(cache_path, batch_id=batch_id, rows=rows, stats=stats)

    customer_n = sum(1 for r in rows if r.get("is_customer"))
    other_n = len(rows) - customer_n
    uniq_tmp = len({(r.get("tmp_openid") or "") for r in rows if r.get("tmp_openid")})
    print(
        f"数据就绪: 明细 {len(rows)} 行, 客户标记 {customer_n}, 其他 {other_n}, "
        f"tmp_openid 去重 {uniq_tmp}, 有添加人的员工 {len(stats)} 人"
    )
    if stats:
        print("添加人 TOP10:")
        for s in stats[:10]:
            print(
                f"  {s['follow_userid']}: 合计 {s['contact_cnt']} "
                f"(客户 {s['customer_cnt']} / 其他 {s['other_cnt']})"
            )

    if args.dry_run:
        print("dry-run：未写库")
        return 0

    print("3) 写库 db_fz_jingnao ...")
    engine = _get_engine()
    ensure_tables(engine)
    if args.keep_old_batches:
        # 追加模式：不删旧批次
        synced_at = datetime.now().replace(microsecond=0)
        insert_contact = text(
            """
            INSERT INTO qywx_served_external_contact (
              sync_batch_id, tmp_openid, external_userid, is_customer, name,
              follow_userid, chat_id, chat_name, add_time, add_time_dt, synced_at
            ) VALUES (
              :sync_batch_id, :tmp_openid, :external_userid, :is_customer, :name,
              :follow_userid, :chat_id, :chat_name, :add_time, :add_time_dt, :synced_at
            )
            """
        )
        insert_stat = text(
            """
            INSERT INTO qywx_served_external_contact_stat (
              sync_batch_id, follow_userid, contact_cnt, customer_cnt, other_cnt, synced_at
            ) VALUES (
              :sync_batch_id, :follow_userid, :contact_cnt, :customer_cnt, :other_cnt, :synced_at
            )
            """
        )
        contact_params = []
        for row in rows:
            add_time = row.get("add_time")
            try:
                add_time_int = int(add_time) if add_time is not None else None
            except (TypeError, ValueError):
                add_time_int = None
            contact_params.append(
                {
                    "sync_batch_id": batch_id,
                    "tmp_openid": (row.get("tmp_openid") or "")[:128],
                    "external_userid": row.get("external_userid"),
                    "is_customer": 1 if row.get("is_customer") else 0,
                    "name": row.get("name"),
                    "follow_userid": row.get("follow_userid"),
                    "chat_id": row.get("chat_id"),
                    "chat_name": row.get("chat_name"),
                    "add_time": add_time_int,
                    "add_time_dt": _ts_to_dt(add_time_int),
                    "synced_at": synced_at,
                }
            )
        with engine.begin() as conn:
            if contact_params:
                conn.execute(insert_contact, contact_params)
            if stats:
                conn.execute(
                    insert_stat,
                    [
                        {
                            "sync_batch_id": batch_id,
                            "follow_userid": s["follow_userid"],
                            "contact_cnt": s["contact_cnt"],
                            "customer_cnt": s["customer_cnt"],
                            "other_cnt": s["other_cnt"],
                            "synced_at": synced_at,
                        }
                        for s in stats
                    ],
                )
    else:
        replace_batch(engine, batch_id=batch_id, rows=rows, stats=stats)

    with engine.connect() as conn:
        n1 = conn.execute(text("SELECT COUNT(*) FROM qywx_served_external_contact")).scalar()
        n2 = conn.execute(text("SELECT COUNT(*) FROM qywx_served_external_contact_stat")).scalar()
    print(f"写库完成: qywx_served_external_contact={n1}, qywx_served_external_contact_stat={n2}")
    print(
        "查询示例:\n"
        "  SELECT follow_userid, contact_cnt, customer_cnt, other_cnt "
        "FROM qywx_served_external_contact_stat ORDER BY contact_cnt DESC LIMIT 20;"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI 出口统一打印
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
