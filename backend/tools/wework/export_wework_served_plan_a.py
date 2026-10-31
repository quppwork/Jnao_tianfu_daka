#!/usr/bin/env python3
"""方案 A：接口原样落 2 张表（明细 + 汇总），不做业务标签字段。

明细表字段 = contact_list 返回字段 + 姓名预留列（空）
汇总表 = 按 follow_userid 对 tmp_openid 去重计数（二次汇总，可选）

用法:
  python backend/tools/export_wework_served_plan_a.py --from-json docs/export/xxx.json
  python backend/tools/export_wework_served_plan_a.py --from-json docs/export/xxx.json --since-days 7
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DDL = r"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

-- 清理旧结构（宽表 / 分表）
DROP TABLE IF EXISTS qywx_fact_served;
DROP TABLE IF EXISTS qywx_stat_follow;
DROP TABLE IF EXISTS qywx_dim_chat;
DROP TABLE IF EXISTS qywx_dim_external_contact;
DROP TABLE IF EXISTS qywx_dim_follow_user;
DROP TABLE IF EXISTS qywx_sync_batch;
DROP TABLE IF EXISTS qywx_served_external_contact;
DROP TABLE IF EXISTS qywx_served_external_contact_stat;
DROP TABLE IF EXISTS qywx_served_record;
DROP TABLE IF EXISTS qywx_served_stat;

-- 明细：尽量保持 contact_list 原字段；姓名列为后续补全预留
CREATE TABLE qywx_served_record (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  is_customer TINYINT(1) NOT NULL DEFAULT 0 COMMENT '接口 is_customer',
  tmp_openid VARCHAR(128) NOT NULL DEFAULT '' COMMENT '接口 tmp_openid',
  external_userid VARCHAR(64) NULL COMMENT '接口 external_userid',
  follow_userid VARCHAR(64) NULL COMMENT '接口 follow_userid',
  chat_id VARCHAR(64) NULL COMMENT '接口 chat_id',
  add_time INT UNSIGNED NULL COMMENT '接口 add_time(秒级时间戳)',
  name VARCHAR(128) NULL COMMENT '接口 name(客户通常为空；后续可补全)',
  chat_name VARCHAR(255) NULL COMMENT '接口 chat_name(常为空；后续可补全)',
  follow_name VARCHAR(128) NULL COMMENT '非接口字段：添加人姓名预留',
  PRIMARY KEY (id),
  KEY idx_external (external_userid),
  KEY idx_follow (follow_userid),
  KEY idx_chat (chat_id),
  KEY idx_add_time (add_time),
  KEY idx_tmp (tmp_openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信contact_list明细(近原样)';

-- 汇总：二次统计，非接口原始字段
CREATE TABLE qywx_served_stat (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NOT NULL COMMENT '员工 userid',
  contact_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'tmp_openid去重人数',
  customer_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  other_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='按添加人汇总(二次统计)';

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


def build_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-json", required=True)
    parser.add_argument("--since-days", type=int, default=0, help="仅筛选最近N天；不写入任何标签字段")
    parser.add_argument("--output", default="")
    parser.add_argument("--skip-stat", action="store_true", help="不生成汇总表数据")
    args = parser.parse_args()

    src = Path(args.from_json)
    data = json.loads(src.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = list(data.get("rows") or [])

    if args.since_days > 0:
        cut = int((datetime.now() - timedelta(days=args.since_days)).timestamp())
        rows = [r for r in rows if (r.get("add_time") or 0) >= cut]

    out = Path(args.output) if args.output else src.with_name(src.stem + "_plan_a.sql")
    if args.since_days > 0 and not args.output:
        out = src.with_name(src.stem + f"_plan_a_{args.since_days}d.sql")

    stats = [] if args.skip_stat else build_stats(rows)

    with out.open("w", encoding="utf-8") as f:
        f.write("-- plan A: raw-ish contact_list fields -> 2 tables\n")
        f.write("-- filter is export-time only; no since_days/batch label columns\n")
        f.write(DDL)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")

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
                            "1" if r.get("is_customer") else "0",
                            _esc((r.get("tmp_openid") or "")[:128]),
                            _esc(r.get("external_userid")),
                            _esc(r.get("follow_userid")),
                            _esc(r.get("chat_id")),
                            _esc(at_i),
                            _esc(r.get("name")),  # 接口原字段，当前多为 NULL
                            _esc(r.get("chat_name")),
                            "NULL",  # follow_name 预留
                        ]
                    )
                    + ")"
                )
            f.write(
                "INSERT INTO qywx_served_record "
                "(is_customer,tmp_openid,external_userid,follow_userid,chat_id,"
                "add_time,name,chat_name,follow_name) VALUES\n"
            )
            f.write(",\n".join(vals))
            f.write(";\n")

        if stats:
            vals = [
                "("
                + ",".join(
                    [
                        _esc(s["follow_userid"]),
                        _esc(s["contact_cnt"]),
                        _esc(s["customer_cnt"]),
                        _esc(s["other_cnt"]),
                    ]
                )
                + ")"
                for s in stats
            ]
            for i in range(0, len(vals), 500):
                f.write(
                    "INSERT INTO qywx_served_stat "
                    "(follow_userid,contact_cnt,customer_cnt,other_cnt) VALUES\n"
                )
                f.write(",\n".join(vals[i : i + 500]))
                f.write(";\n")

        f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    print(f"输出: {out} ({out.stat().st_size // 1024} KB)")
    print(f"明细 {len(rows)} 行, 汇总 {len(stats)} 人")
    print("二次处理说明:")
    print("  - 若加了 --since-days：只是导出时按 add_time 过滤，库里不写该标签")
    print("  - qywx_served_stat：按 follow_userid 去重统计，非接口原表")
    print("  - follow_name：预留列，当前全 NULL")
    print("  - 其余明细列对应接口原字段（name/chat_name 接口本身常不返回）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
