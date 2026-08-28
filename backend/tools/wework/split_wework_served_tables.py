#!/usr/bin/env python3
"""把已服务外部联系人缓存拆成多张维度/事实表，姓名字段留空便于后续补全。

表结构：
  qywx_sync_batch              同步批次
  qywx_dim_follow_user         添加人（员工）维度  — follow_name 待补
  qywx_dim_external_contact    外部联系人维度      — name 待补
  qywx_dim_chat                外部群维度          — chat_name 待补
  qywx_fact_served             已服务关系事实表
  qywx_stat_follow             按添加人汇总

用法:
  python backend/tools/split_wework_served_tables.py --from-json docs/export/qywx_served_contacts_XXXX.json
  python backend/tools/split_wework_served_tables.py --from-json ... --since-days 7
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


DDL = r"""
-- 企业微信已服务外部联系人：分表结构（姓名后续补全）
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS qywx_fact_served;
DROP TABLE IF EXISTS qywx_stat_follow;
DROP TABLE IF EXISTS qywx_dim_chat;
DROP TABLE IF EXISTS qywx_dim_external_contact;
DROP TABLE IF EXISTS qywx_dim_follow_user;
DROP TABLE IF EXISTS qywx_sync_batch;
-- 旧两张宽表（若存在可一并清掉，避免混淆）
DROP TABLE IF EXISTS qywx_served_external_contact;
DROP TABLE IF EXISTS qywx_served_external_contact_stat;

CREATE TABLE qywx_sync_batch (
  batch_id VARCHAR(32) NOT NULL COMMENT '同步批次',
  fetched_at DATETIME NULL COMMENT '拉取时间',
  row_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '事实表行数',
  follow_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  external_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  chat_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  PRIMARY KEY (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信同步批次';

CREATE TABLE qywx_dim_follow_user (
  follow_userid VARCHAR(64) NOT NULL COMMENT '员工 userid',
  follow_name VARCHAR(128) NULL COMMENT '员工姓名(待补全)',
  first_seen_batch VARCHAR(32) NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (follow_userid),
  KEY idx_follow_name (follow_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='添加人维度';

CREATE TABLE qywx_dim_external_contact (
  external_userid VARCHAR(64) NOT NULL COMMENT '外部联系人ID',
  tmp_openid VARCHAR(128) NULL COMMENT '最近一次同步临时ID',
  name VARCHAR(128) NULL COMMENT '外部联系人姓名(待补全)',
  is_customer TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否客户',
  first_seen_batch VARCHAR(32) NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (external_userid),
  KEY idx_name (name),
  KEY idx_tmp (tmp_openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='外部联系人维度';

CREATE TABLE qywx_dim_chat (
  chat_id VARCHAR(64) NOT NULL COMMENT '群ID',
  chat_name VARCHAR(255) NULL COMMENT '群名(待补全)',
  first_seen_batch VARCHAR(32) NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (chat_id),
  KEY idx_chat_name (chat_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='外部群维度';

CREATE TABLE qywx_fact_served (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sync_batch_id VARCHAR(32) NOT NULL,
  tmp_openid VARCHAR(128) NOT NULL DEFAULT '',
  external_userid VARCHAR(64) NULL,
  follow_userid VARCHAR(64) NULL,
  chat_id VARCHAR(64) NULL,
  is_customer TINYINT(1) NOT NULL DEFAULT 0,
  add_time INT UNSIGNED NULL,
  add_time_dt DATETIME NULL,
  synced_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_batch (sync_batch_id),
  KEY idx_external (external_userid),
  KEY idx_follow (follow_userid),
  KEY idx_chat (chat_id),
  KEY idx_add_time (add_time),
  KEY idx_add_dt (add_time_dt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='已服务关系事实表(无姓名，靠维度表关联)';

CREATE TABLE qywx_stat_follow (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sync_batch_id VARCHAR(32) NOT NULL,
  follow_userid VARCHAR(64) NOT NULL,
  contact_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '去重外部联系人数',
  customer_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  other_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  synced_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_follow (sync_batch_id, follow_userid),
  KEY idx_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='按添加人汇总';

SET FOREIGN_KEY_CHECKS=1;
"""


def _esc(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(int(v))
    s = str(v).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def _ts_to_dt(ts: Any) -> str | None:
    if ts is None or ts == "":
        return None
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def build_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict

    by: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"all": set(), "c": set(), "o": set()})
    for r in rows:
        uid = (r.get("follow_userid") or "").strip()
        if not uid:
            continue
        key = (r.get("tmp_openid") or r.get("external_userid") or "").strip()
        if not key:
            continue
        by[uid]["all"].add(key)
        if r.get("is_customer"):
            by[uid]["c"].add(key)
        else:
            by[uid]["o"].add(key)
    return [
        {
            "follow_userid": uid,
            "contact_cnt": len(s["all"]),
            "customer_cnt": len(s["c"]),
            "other_cnt": len(s["o"]),
        }
        for uid, s in sorted(by.items(), key=lambda x: (-len(x[1]["all"]), x[0]))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分企业微信已服务联系人为多表 SQL")
    parser.add_argument("--from-json", required=True)
    parser.add_argument("--since-days", type=int, default=0, help="只导出最近 N 天（0=全部）")
    parser.add_argument("--output", type=str, default="", help="输出 SQL 路径")
    args = parser.parse_args()

    src = Path(args.from_json)
    data = json.loads(src.read_text(encoding="utf-8"))
    batch_id = str(data.get("batch_id") or datetime.now().strftime("%Y%m%d%H%M%S"))
    rows: list[dict[str, Any]] = list(data.get("rows") or [])

    note = "full"
    if args.since_days and args.since_days > 0:
        cut = int((datetime.now() - timedelta(days=args.since_days)).timestamp())
        rows = [r for r in rows if (r.get("add_time") or 0) >= cut]
        note = f"since_{args.since_days}d"
        batch_id = f"{batch_id}_{note}"

    stats = list(data.get("stats") or []) if not args.since_days else build_stats(rows)

    follow_ids = sorted({(r.get("follow_userid") or "").strip() for r in rows if r.get("follow_userid")})
    # 外部联系人：优先 external_userid；无则跳过进维度（仍进事实表）
    external_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        eid = (r.get("external_userid") or "").strip()
        if not eid:
            continue
        prev = external_map.get(eid)
        if not prev:
            external_map[eid] = {
                "external_userid": eid,
                "tmp_openid": (r.get("tmp_openid") or "")[:128],
                "is_customer": 1 if r.get("is_customer") else 0,
            }
    chat_ids = sorted({(r.get("chat_id") or "").strip() for r in rows if r.get("chat_id")})

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fetched_at = data.get("fetched_at") or now

    suffix = f"_{note}" if args.since_days else "_split"
    out = Path(args.output) if args.output else src.with_name(src.stem + suffix + ".sql")

    with out.open("w", encoding="utf-8") as f:
        f.write(DDL)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")

        f.write(
            "INSERT INTO qywx_sync_batch "
            "(batch_id,fetched_at,row_count,follow_cnt,external_cnt,chat_cnt,note,created_at) VALUES ("
            + ",".join(
                [
                    _esc(batch_id),
                    _esc(str(fetched_at)[:19].replace("T", " ")),
                    _esc(len(rows)),
                    _esc(len(follow_ids)),
                    _esc(len(external_map)),
                    _esc(len(chat_ids)),
                    _esc(note),
                    _esc(now),
                ]
            )
            + ");\n"
        )

        # dim follow
        if follow_ids:
            vals = [
                f"({_esc(uid)},NULL,{_esc(batch_id)},{_esc(now)})" for uid in follow_ids
            ]
            for i in range(0, len(vals), 500):
                f.write(
                    "INSERT INTO qywx_dim_follow_user "
                    "(follow_userid,follow_name,first_seen_batch,updated_at) VALUES\n"
                )
                f.write(",\n".join(vals[i : i + 500]))
                f.write(";\n")

        # dim external
        ext_list = list(external_map.values())
        for i in range(0, len(ext_list), 500):
            chunk = ext_list[i : i + 500]
            vals = [
                "("
                + ",".join(
                    [
                        _esc(e["external_userid"]),
                        _esc(e["tmp_openid"] or None),
                        "NULL",
                        _esc(e["is_customer"]),
                        _esc(batch_id),
                        _esc(now),
                    ]
                )
                + ")"
                for e in chunk
            ]
            f.write(
                "INSERT INTO qywx_dim_external_contact "
                "(external_userid,tmp_openid,name,is_customer,first_seen_batch,updated_at) VALUES\n"
            )
            f.write(",\n".join(vals))
            f.write(";\n")

        # dim chat
        if chat_ids:
            vals = [f"({_esc(cid)},NULL,{_esc(batch_id)},{_esc(now)})" for cid in chat_ids]
            for i in range(0, len(vals), 500):
                f.write(
                    "INSERT INTO qywx_dim_chat (chat_id,chat_name,first_seen_batch,updated_at) VALUES\n"
                )
                f.write(",\n".join(vals[i : i + 500]))
                f.write(";\n")

        # fact
        for i in range(0, len(rows), 400):
            chunk = rows[i : i + 400]
            vals = []
            for r in chunk:
                at = r.get("add_time")
                try:
                    at_i = int(at) if at is not None else None
                except (TypeError, ValueError):
                    at_i = None
                vals.append(
                    "("
                    + ",".join(
                        [
                            _esc(batch_id),
                            _esc((r.get("tmp_openid") or "")[:128]),
                            _esc(r.get("external_userid")),
                            _esc(r.get("follow_userid")),
                            _esc(r.get("chat_id")),
                            "1" if r.get("is_customer") else "0",
                            _esc(at_i),
                            _esc(_ts_to_dt(at_i)),
                            _esc(now),
                        ]
                    )
                    + ")"
                )
            f.write(
                "INSERT INTO qywx_fact_served "
                "(sync_batch_id,tmp_openid,external_userid,follow_userid,chat_id,"
                "is_customer,add_time,add_time_dt,synced_at) VALUES\n"
            )
            f.write(",\n".join(vals))
            f.write(";\n")

        # stat
        if stats:
            # 若全量缓存自带 stats 且未按时间过滤，直接用；否则上面已 rebuild
            use_stats = stats
            if args.since_days:
                use_stats = build_stats(rows)
            vals = [
                "("
                + ",".join(
                    [
                        _esc(batch_id),
                        _esc(s["follow_userid"]),
                        _esc(s["contact_cnt"]),
                        _esc(s["customer_cnt"]),
                        _esc(s["other_cnt"]),
                        _esc(now),
                    ]
                )
                + ")"
                for s in use_stats
                if s.get("follow_userid")
            ]
            for i in range(0, len(vals), 500):
                f.write(
                    "INSERT INTO qywx_stat_follow "
                    "(sync_batch_id,follow_userid,contact_cnt,customer_cnt,other_cnt,synced_at) VALUES\n"
                )
                f.write(",\n".join(vals[i : i + 500]))
                f.write(";\n")

        f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    print(f"输出: {out} ({out.stat().st_size // 1024} KB)")
    print(
        f"批次 {batch_id}: fact={len(rows)} follow={len(follow_ids)} "
        f"external={len(external_map)} chat={len(chat_ids)} note={note}"
    )
    print(
        "查询示例:\n"
        "  SELECT f.add_time_dt, e.external_userid, e.name AS 客户名,\n"
        "         u.follow_userid, u.follow_name AS 添加人, c.chat_name AS 群名\n"
        "  FROM qywx_fact_served f\n"
        "  LEFT JOIN qywx_dim_external_contact e ON e.external_userid=f.external_userid\n"
        "  LEFT JOIN qywx_dim_follow_user u ON u.follow_userid=f.follow_userid\n"
        "  LEFT JOIN qywx_dim_chat c ON c.chat_id=f.chat_id\n"
        "  ORDER BY f.add_time DESC LIMIT 20;"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
