#!/usr/bin/env python3
"""用 batch/get_by_user 按员工拉客户详情，写入独立新表（不 DROP 其它表）。

POST /cgi-bin/externalcontact/batch/get_by_user

用法:
  python -u backend/tools/fetch_wework_batch_by_user.py --from-json docs/export/xxx_plan_a_7d_enriched.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
TABLE = "qywx_external_contact_batch"


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


def load_follow_ids(path: Path, since_days: int) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = list(data.get("rows") or [])
    if since_days > 0:
        cut = int((datetime.now() - timedelta(days=since_days)).timestamp())
        rows = [r for r in rows if (r.get("add_time") or 0) >= cut]
    # 优先用 stat，否则从 rows 抽
    stats = data.get("stats") or []
    ids = sorted(
        {
            (s.get("follow_userid") or "").strip()
            for s in stats
            if s.get("follow_userid")
        }
        | {(r.get("follow_userid") or "").strip() for r in rows if r.get("follow_userid")}
    )
    return [x for x in ids if x]


def fetch_by_user(token: str, userid: str) -> list[dict[str, Any]]:
    """返回 [{follow_userid, external_contact, follow_info}, ...]"""
    out: list[dict[str, Any]] = []
    cursor = ""
    while True:
        payload: dict[str, Any] = {"userid_list": [userid], "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        d = requests.post(
            f"{QYAPI}/externalcontact/batch/get_by_user",
            params={"access_token": token},
            json=payload,
            timeout=60,
        ).json()
        if d.get("errcode", 0) != 0:
            print(f"  [warn] {userid}: {d.get('errcode')} {d.get('errmsg')}", flush=True)
            break
        for item in d.get("external_contact_list") or []:
            out.append(
                {
                    "follow_userid": userid,
                    "external_contact": item.get("external_contact") or {},
                    "follow_info": item.get("follow_info") or {},
                }
            )
        cursor = (d.get("next_cursor") or "").strip()
        if not cursor:
            break
        time.sleep(0.03)
    return out


def flatten(item: dict[str, Any]) -> dict[str, Any]:
    ec = item.get("external_contact") or {}
    fi = item.get("follow_info") or {}
    return {
        "follow_userid": item.get("follow_userid"),
        "external_userid": ec.get("external_userid"),
        "name": ec.get("name"),
        "avatar": ec.get("avatar"),
        "type": ec.get("type"),
        "gender": ec.get("gender"),
        "unionid": ec.get("unionid"),
        "position": ec.get("position"),
        "corp_name": ec.get("corp_name"),
        "corp_full_name": ec.get("corp_full_name"),
        "follow_remark": fi.get("remark"),
        "follow_description": fi.get("description"),
        "follow_createtime": fi.get("createtime"),
        "follow_add_way": fi.get("add_way"),
        "follow_oper_userid": fi.get("oper_userid"),
        "follow_remark_corp_name": fi.get("remark_corp_name"),
        "follow_tag_ids": ",".join(fi.get("tag_id") or []) if fi.get("tag_id") else None,
        "external_contact_json": json.dumps(ec, ensure_ascii=False),
        "follow_info_json": json.dumps(fi, ensure_ascii=False),
    }


def write_sql(path: Path, rows: list[dict[str, Any]]) -> None:
    """只建/重建本表，绝不 DROP qywx_served_record / qywx_served_stat。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ddl = f"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

-- 仅操作本表，不影响 qywx_served_record / qywx_served_stat
DROP TABLE IF EXISTS {TABLE};
CREATE TABLE {TABLE} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NOT NULL COMMENT '员工userid(批量查询入参)',
  external_userid VARCHAR(64) NOT NULL COMMENT '客户external_userid',
  name VARCHAR(128) NULL COMMENT '客户名称',
  avatar VARCHAR(512) NULL,
  type TINYINT NULL COMMENT '1微信用户 2企业微信用户',
  gender TINYINT NULL,
  unionid VARCHAR(64) NULL,
  position VARCHAR(128) NULL,
  corp_name VARCHAR(128) NULL,
  corp_full_name VARCHAR(255) NULL,
  follow_remark VARCHAR(255) NULL COMMENT '跟进人备注',
  follow_description VARCHAR(512) NULL,
  follow_createtime INT UNSIGNED NULL COMMENT '添加时间戳',
  follow_add_way INT NULL COMMENT '添加来源',
  follow_oper_userid VARCHAR(64) NULL,
  follow_remark_corp_name VARCHAR(128) NULL,
  follow_tag_ids TEXT NULL,
  external_contact_json MEDIUMTEXT NULL,
  follow_info_json MEDIUMTEXT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_follow_external (follow_userid, external_userid),
  KEY idx_external (external_userid),
  KEY idx_name (name),
  KEY idx_follow (follow_userid),
  KEY idx_createtime (follow_createtime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='batch/get_by_user 客户详情(独立表)';

SET FOREIGN_KEY_CHECKS=1;
"""
    with path.open("w", encoding="utf-8") as f:
        f.write("-- batch/get_by_user only; does NOT touch served_record/stat\n")
        f.write(ddl)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        cols = (
            "follow_userid,external_userid,name,avatar,type,gender,unionid,position,"
            "corp_name,corp_full_name,follow_remark,follow_description,follow_createtime,"
            "follow_add_way,follow_oper_userid,follow_remark_corp_name,follow_tag_ids,"
            "external_contact_json,follow_info_json,fetched_at"
        )
        for i in range(0, len(rows), 80):
            chunk = rows[i : i + 80]
            vals = []
            for r in chunk:
                if not r.get("external_userid"):
                    continue
                vals.append(
                    "("
                    + ",".join(
                        [
                            _esc(r.get("follow_userid")),
                            _esc(r.get("external_userid")),
                            _esc(r.get("name")),
                            _esc(r.get("avatar")),
                            _esc(r.get("type")),
                            _esc(r.get("gender")),
                            _esc(r.get("unionid")),
                            _esc(r.get("position")),
                            _esc(r.get("corp_name")),
                            _esc(r.get("corp_full_name")),
                            _esc(r.get("follow_remark")),
                            _esc(r.get("follow_description")),
                            _esc(r.get("follow_createtime")),
                            _esc(r.get("follow_add_way")),
                            _esc(r.get("follow_oper_userid")),
                            _esc(r.get("follow_remark_corp_name")),
                            _esc(r.get("follow_tag_ids")),
                            _esc(r.get("external_contact_json")),
                            _esc(r.get("follow_info_json")),
                            _esc(now),
                        ]
                    )
                    + ")"
                )
            if not vals:
                continue
            f.write(f"INSERT INTO {TABLE} ({cols}) VALUES\n")
            f.write(",\n".join(vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--since-days", type=int, default=0)
    args = ap.parse_args()

    src = Path(args.from_json)
    follow_ids = load_follow_ids(src, args.since_days)
    print(f"员工数 follow_userid={len(follow_ids)}", flush=True)

    token = get_token()
    flats: list[dict[str, Any]] = []
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = ROOT / "docs" / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"qywx_external_batch_{stamp}.json"
    out_sql = out_dir / f"qywx_external_batch_{stamp}.sql"

    def _flush() -> None:
        out_json.write_text(
            json.dumps({"table": TABLE, "count": len(flats), "rows": flats}, ensure_ascii=False),
            encoding="utf-8",
        )
        write_sql(out_sql, flats)

    for i, uid in enumerate(follow_ids, 1):
        items = fetch_by_user(token, uid)
        for it in items:
            flats.append(flatten(it))
        print(f"  {i}/{len(follow_ids)} {uid}: +{len(items)} 累计 {len(flats)}", flush=True)
        if i % 5 == 0 or i == len(follow_ids):
            _flush()
            print(f"  checkpoint -> {out_sql.name}", flush=True)
        time.sleep(0.05)

    _flush()
    named = sum(1 for r in flats if r.get("name"))
    print(f"完成: {len(flats)} 条, 有姓名 {named}", flush=True)
    print(f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)", flush=True)
    print(f"已写 {out_json}", flush=True)
    print(
        f"导入（只建 {TABLE}，不覆盖 served 两表）:\n"
        f"  mysql -h ... -u jingnao -p db_fz_jingnao < {out_sql.name}\n"
        f"查询:\n"
        f"  SELECT name, follow_userid, FROM_UNIXTIME(follow_createtime) AS added_at\n"
        f"  FROM {TABLE} ORDER BY follow_createtime DESC LIMIT 20;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
