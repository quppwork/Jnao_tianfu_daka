#!/usr/bin/env python3
"""近 N 天 contact_list 明细补全姓名/群名，输出方案 A 两表 SQL（可直观查询）。

补全：
  name         <- batch/get_by_user + externalcontact/get
  follow_name  <- user/get
  chat_name    <- groupchat/get

用法:
  python -u backend/tools/enrich_wework_plan_a_recent.py --from-json docs/export/xxx.json --since-days 7
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
load_dotenv(BACKEND / ".env", override=False)
load_dotenv(ROOT / ".env", override=False)

QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"


def _env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise RuntimeError(f"缺少环境变量 {name}")
    return v


def _esc(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(int(v))
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def get_token() -> str:
    r = requests.get(
        f"{QYAPI}/gettoken",
        params={"corpid": _env("WEWORK_CORPID"), "corpsecret": _env("WEWORK_CORPSECRET")},
        timeout=30,
    )
    d = r.json()
    if d.get("errcode", 0) != 0:
        raise RuntimeError(d)
    return d["access_token"]


def fetch_follow_names(token: str, uids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, uid in enumerate(uids, 1):
        d = requests.get(
            f"{QYAPI}/user/get",
            params={"access_token": token, "userid": uid},
            timeout=30,
        ).json()
        if d.get("errcode", 0) == 0 and d.get("name"):
            out[uid] = str(d["name"])
        print(f"  follow {i}/{len(uids)} ok={len(out)}", flush=True)
        time.sleep(0.04)
    return out


def fetch_external_names(token: str, follow_uids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, uid in enumerate(follow_uids, 1):
        cursor = ""
        while True:
            payload: dict[str, Any] = {"userid_list": [uid], "limit": 100}
            if cursor:
                payload["cursor"] = cursor
            d = requests.post(
                f"{QYAPI}/externalcontact/batch/get_by_user",
                params={"access_token": token},
                json=payload,
                timeout=60,
            ).json()
            if d.get("errcode", 0) != 0:
                print(f"  [warn] batch {uid}: {d.get('errcode')} {d.get('errmsg')}", flush=True)
                break
            for item in d.get("external_contact_list") or []:
                ec = item.get("external_contact") or {}
                eid, name = (ec.get("external_userid") or "").strip(), (ec.get("name") or "").strip()
                if eid and name:
                    out[eid] = name
            cursor = (d.get("next_cursor") or "").strip()
            if not cursor:
                break
            time.sleep(0.03)
        print(f"  external via follow {i}/{len(follow_uids)} mapped={len(out)}", flush=True)
        time.sleep(0.04)
    return out


def fetch_external_missing(token: str, eids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, eid in enumerate(eids, 1):
        d = requests.get(
            f"{QYAPI}/externalcontact/get",
            params={"access_token": token, "external_userid": eid},
            timeout=30,
        ).json()
        if d.get("errcode", 0) == 0:
            name = ((d.get("external_contact") or {}).get("name") or "").strip()
            if name:
                out[eid] = name
        if i % 50 == 0 or i == len(eids):
            print(f"  external get {i}/{len(eids)} ok={len(out)}", flush=True)
        time.sleep(0.04)
    return out


def fetch_chat_names(token: str, cids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, cid in enumerate(cids, 1):
        d = requests.post(
            f"{QYAPI}/externalcontact/groupchat/get",
            params={"access_token": token},
            json={"chat_id": cid, "need_name": 0},
            timeout=30,
        ).json()
        if d.get("errcode", 0) == 0:
            name = ((d.get("group_chat") or {}).get("name") or "").strip()
            if name:
                out[cid] = name
        if i % 20 == 0 or i == len(cids):
            print(f"  chat {i}/{len(cids)} ok={len(out)}", flush=True)
        time.sleep(0.04)
    return out


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
        (by[uid]["c"] if r.get("is_customer") else by[uid]["o"]).add(key)
    return [
        {
            "follow_userid": u,
            "follow_name": None,
            "contact_cnt": len(s["all"]),
            "customer_cnt": len(s["c"]),
            "other_cnt": len(s["o"]),
        }
        for u, s in sorted(by.items(), key=lambda x: (-len(x[1]["all"]), x[0]))
    ]


def write_sql(path: Path, rows: list[dict[str, Any]], stats: list[dict[str, Any]]) -> None:
    ddl = r"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
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

CREATE TABLE qywx_served_record (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  is_customer TINYINT(1) NOT NULL DEFAULT 0,
  tmp_openid VARCHAR(128) NOT NULL DEFAULT '',
  external_userid VARCHAR(64) NULL,
  follow_userid VARCHAR(64) NULL,
  chat_id VARCHAR(64) NULL,
  add_time INT UNSIGNED NULL,
  name VARCHAR(128) NULL COMMENT '外部联系人名称',
  follow_name VARCHAR(128) NULL COMMENT '添加人姓名',
  chat_name VARCHAR(255) NULL COMMENT '加入的外部群',
  PRIMARY KEY (id),
  KEY idx_add_time (add_time),
  KEY idx_follow (follow_userid),
  KEY idx_external (external_userid),
  KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='已服务外部联系人(含展示名)';

CREATE TABLE qywx_served_stat (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NOT NULL,
  follow_name VARCHAR(128) NULL,
  contact_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  customer_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  other_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='按添加人汇总';
"""
    with path.open("w", encoding="utf-8") as f:
        f.write(ddl)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        for i in range(0, len(rows), 300):
            chunk = rows[i : i + 300]
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
                            _esc(r.get("name")),
                            _esc(r.get("follow_name")),
                            _esc(r.get("chat_name")),
                        ]
                    )
                    + ")"
                )
            f.write(
                "INSERT INTO qywx_served_record "
                "(is_customer,tmp_openid,external_userid,follow_userid,chat_id,"
                "add_time,name,follow_name,chat_name) VALUES\n"
            )
            f.write(",\n".join(vals) + ";\n")
        if stats:
            vals = [
                "("
                + ",".join(
                    [
                        _esc(s["follow_userid"]),
                        _esc(s.get("follow_name")),
                        _esc(s["contact_cnt"]),
                        _esc(s["customer_cnt"]),
                        _esc(s["other_cnt"]),
                    ]
                )
                + ")"
                for s in stats
            ]
            f.write(
                "INSERT INTO qywx_served_stat "
                "(follow_userid,follow_name,contact_cnt,customer_cnt,other_cnt) VALUES\n"
            )
            f.write(",\n".join(vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--since-days", type=int, default=7)
    args = ap.parse_args()

    src = Path(args.from_json)
    data = json.loads(src.read_text(encoding="utf-8"))
    rows = list(data.get("rows") or [])
    cut = int((datetime.now() - timedelta(days=args.since_days)).timestamp())
    rows = [r for r in rows if (r.get("add_time") or 0) >= cut]

    follow_ids = sorted({(r.get("follow_userid") or "").strip() for r in rows if r.get("follow_userid")})
    external_ids = sorted({(r.get("external_userid") or "").strip() for r in rows if r.get("external_userid")})
    chat_ids = sorted({(r.get("chat_id") or "").strip() for r in rows if r.get("chat_id")})
    print(
        f"近{args.since_days}天: rows={len(rows)} follow={len(follow_ids)} "
        f"external={len(external_ids)} chat={len(chat_ids)}",
        flush=True,
    )

    token = get_token()
    print("1) 添加人姓名", flush=True)
    follow_names = fetch_follow_names(token, follow_ids)
    print("2) 客户姓名(按添加人批量)", flush=True)
    external_names = fetch_external_names(token, follow_ids)
    missing = [e for e in external_ids if e not in external_names]
    if missing:
        print(f"3) 客户姓名补漏 {len(missing)}", flush=True)
        external_names.update(fetch_external_missing(token, missing))
    else:
        print("3) 无需补漏", flush=True)
    print("4) 群名", flush=True)
    chat_names = fetch_chat_names(token, chat_ids) if chat_ids else {}

    for r in rows:
        eid = (r.get("external_userid") or "").strip()
        fid = (r.get("follow_userid") or "").strip()
        cid = (r.get("chat_id") or "").strip()
        if eid in external_names:
            r["name"] = external_names[eid]
        if fid in follow_names:
            r["follow_name"] = follow_names[fid]
        if cid in chat_names:
            r["chat_name"] = chat_names[cid]

    stats = build_stats(rows)
    for s in stats:
        s["follow_name"] = follow_names.get(s["follow_userid"])

    n_name = sum(1 for r in rows if r.get("name"))
    n_fn = sum(1 for r in rows if r.get("follow_name"))
    n_cn = sum(1 for r in rows if r.get("chat_name"))
    print(f"补全: name={n_name}/{len(rows)} follow_name={n_fn}/{len(rows)} chat_name={n_cn}/{len(rows)}", flush=True)

    out_sql = src.with_name(src.stem + f"_plan_a_{args.since_days}d_enriched.sql")
    out_json = src.with_name(src.stem + f"_plan_a_{args.since_days}d_enriched.json")
    write_sql(out_sql, rows, stats)
    out_json.write_text(
        json.dumps({"rows": rows, "stats": stats, "since_days": args.since_days}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)", flush=True)
    print(f"已写 {out_json}", flush=True)
    print(
        "导入后查询:\n"
        "  SELECT name AS 外部联系人名称,\n"
        "         FROM_UNIXTIME(add_time, '%Y年%c月%e日') AS 首次添加进群时间,\n"
        "         IFNULL(follow_name, '--') AS 添加人,\n"
        "         IFNULL(chat_name, '--') AS 加入的外部群\n"
        "  FROM qywx_served_record\n"
        "  ORDER BY add_time DESC LIMIT 50;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
