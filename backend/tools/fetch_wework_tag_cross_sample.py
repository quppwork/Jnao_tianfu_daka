#!/usr/bin/env python3
"""拉取企业标签库，并与今日样例表最近 10 条客户按 tag_id 交叉关联。

新建表（不修改 qywx_external_contact_full / served_*）:
  qywx_corp_tag                 标签库
  qywx_contact_tag_link_sample  最近10条客户×标签

用法:
  python -u backend/tools/fetch_wework_tag_cross_sample.py --from-json docs/export/qywx_external_full_today10_XXXX.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
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
        raise RuntimeError(f"缺少 {name}")
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
    d = requests.get(
        f"{QYAPI}/gettoken",
        params={"corpid": _env("WEWORK_CORPID"), "corpsecret": _env("WEWORK_CORPSECRET")},
        timeout=30,
    ).json()
    if d.get("errcode", 0) != 0:
        raise RuntimeError(d)
    return d["access_token"]


def fetch_tag_map(token: str) -> dict[str, dict[str, Any]]:
    d = requests.post(
        f"{QYAPI}/externalcontact/get_corp_tag_list",
        params={"access_token": token},
        json={},
        timeout=30,
    ).json()
    if d.get("errcode", 0) != 0:
        raise RuntimeError(d)
    tag_map: dict[str, dict[str, Any]] = {}
    for g in d.get("tag_group") or []:
        for t in g.get("tag") or []:
            tid = t.get("id")
            if not tid:
                continue
            tag_map[tid] = {
                "tag_name": t.get("name"),
                "group_name": g.get("group_name"),
                "group_id": g.get("group_id"),
                "order": t.get("order"),
            }
    return tag_map


def parse_tag_ids(row: dict[str, Any]) -> list[str]:
    raw = row.get("tag_id_json")
    tids: list[str] = []
    if raw:
        try:
            tids = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        except json.JSONDecodeError:
            tids = []
    if not tids and row.get("follow_info_json"):
        try:
            fi = json.loads(row["follow_info_json"])
            tids = list(fi.get("tag_id") or [])
        except json.JSONDecodeError:
            pass
    return [str(x) for x in tids if x]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", default="")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    if args.from_json:
        src = Path(args.from_json)
    else:
        files = sorted((ROOT / "docs" / "export").glob("qywx_external_full_today10_*.json"))
        if not files:
            raise RuntimeError("未找到 qywx_external_full_today10_*.json")
        src = files[-1]

    rows = json.loads(src.read_text(encoding="utf-8")).get("rows") or []
    rows = sorted(rows, key=lambda r: r.get("createtime") or 0, reverse=True)[: args.limit]
    print(f"源文件 {src.name}，取最近 {len(rows)} 条", flush=True)

    token = get_token()
    tag_map = fetch_tag_map(token)
    print(f"标签库 tag 数={len(tag_map)}", flush=True)

    link_rows: list[dict[str, Any]] = []
    for r in rows:
        tids = parse_tag_ids(r)
        base = {
            "follow_userid": r.get("follow_userid"),
            "external_userid": r.get("external_userid"),
            "name": r.get("name"),
            "remark": r.get("remark"),
            "createtime": r.get("createtime"),
            "add_way": r.get("add_way"),
            "state": r.get("state"),
        }
        if not tids:
            link_rows.append({**base, "tag_id": None, "tag_name": None, "group_name": None, "group_id": None})
        else:
            for tid in tids:
                info = tag_map.get(tid) or {}
                link_rows.append(
                    {
                        **base,
                        "tag_id": tid,
                        "tag_name": info.get("tag_name"),
                        "group_name": info.get("group_name"),
                        "group_id": info.get("group_id"),
                    }
                )

    for x in link_rows:
        print(
            f"  {x.get('name')} | tag={x.get('tag_id')} -> {x.get('group_name')}/{x.get('tag_name')}",
            flush=True,
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out = ROOT / "docs" / "export" / f"qywx_tag_cross_recent10_{stamp}.sql"
    with out.open("w", encoding="utf-8") as f:
        f.write("-- get_corp_tag_list + cross recent 10; own tables only\n")
        f.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
        f.write("DROP TABLE IF EXISTS qywx_corp_tag;\n")
        f.write("DROP TABLE IF EXISTS qywx_contact_tag_link_sample;\n")
        f.write(
            """
CREATE TABLE qywx_corp_tag (
  tag_id VARCHAR(64) NOT NULL,
  tag_name VARCHAR(128) NULL,
  group_id VARCHAR(64) NULL,
  group_name VARCHAR(128) NULL,
  tag_order INT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (tag_id),
  KEY idx_group (group_id),
  KEY idx_name (tag_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业客户标签库';

CREATE TABLE qywx_contact_tag_link_sample (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NULL,
  external_userid VARCHAR(64) NULL,
  name VARCHAR(128) NULL,
  remark VARCHAR(255) NULL,
  createtime INT UNSIGNED NULL,
  add_way INT NULL,
  state VARCHAR(128) NULL,
  tag_id VARCHAR(64) NULL,
  tag_name VARCHAR(128) NULL,
  group_id VARCHAR(64) NULL,
  group_name VARCHAR(128) NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_external (external_userid),
  KEY idx_tag (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='最近10条客户与标签交叉样例';
"""
        )
        tag_vals = [
            "("
            + ",".join(
                [
                    _esc(tid),
                    _esc(info.get("tag_name")),
                    _esc(info.get("group_id")),
                    _esc(info.get("group_name")),
                    _esc(info.get("order")),
                    _esc(now),
                ]
            )
            + ")"
            for tid, info in tag_map.items()
        ]
        for i in range(0, len(tag_vals), 100):
            f.write(
                "INSERT INTO qywx_corp_tag "
                "(tag_id,tag_name,group_id,group_name,tag_order,fetched_at) VALUES\n"
            )
            f.write(",\n".join(tag_vals[i : i + 100]) + ";\n")

        link_vals = [
            "("
            + ",".join(
                [
                    _esc(r.get("follow_userid")),
                    _esc(r.get("external_userid")),
                    _esc(r.get("name")),
                    _esc(r.get("remark")),
                    _esc(r.get("createtime")),
                    _esc(r.get("add_way")),
                    _esc(r.get("state")),
                    _esc(r.get("tag_id")),
                    _esc(r.get("tag_name")),
                    _esc(r.get("group_id")),
                    _esc(r.get("group_name")),
                    _esc(now),
                ]
            )
            + ")"
            for r in link_rows
        ]
        if link_vals:
            f.write(
                "INSERT INTO qywx_contact_tag_link_sample "
                "(follow_userid,external_userid,name,remark,createtime,add_way,state,"
                "tag_id,tag_name,group_id,group_name,fetched_at) VALUES\n"
            )
            f.write(",\n".join(link_vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    print(f"已写 {out} ({out.stat().st_size // 1024} KB)", flush=True)
    print(
        "导入后查询:\n"
        "  SELECT name, remark, tag_id, group_name, tag_name\n"
        "  FROM qywx_contact_tag_link_sample;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
