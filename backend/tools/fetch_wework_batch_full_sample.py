#!/usr/bin/env python3
"""按官方 batch/get_by_user 完整字段，拉「今天活跃」的 N 个添加人客户详情。

独立表 qywx_external_contact_full（不碰 served_* / qywx_external_contact_batch）。

用法:
  python -u backend/tools/fetch_wework_batch_full_sample.py --from-json docs/export/xxx_plan_a_7d_enriched.json --people 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
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
TABLE = "qywx_external_contact_full"


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


def today_scope(path: Path, people: int, day: datetime) -> tuple[list[str], set[tuple[str, str]]]:
    """返回：今天 TOP N 添加人；以及 (follow_userid, external_userid) 今日出现过的集合。"""
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    start = int(day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end = start + 86400
    today = [r for r in rows if start <= (r.get("add_time") or 0) < end]
    cnt = Counter((r.get("follow_userid") or "").strip() for r in today if r.get("follow_userid"))
    ids = [uid for uid, _ in cnt.most_common(people)]
    id_set = set(ids)
    pairs: set[tuple[str, str]] = set()
    for r in today:
        fid = (r.get("follow_userid") or "").strip()
        eid = (r.get("external_userid") or "").strip()
        if fid in id_set and eid:
            pairs.add((fid, eid))
    print(
        f"日期 {day.date()} 活跃行={len(today)}，选取添加人 {len(ids)}，"
        f"今日客户对 {len(pairs)}: {ids}",
        flush=True,
    )
    return ids, pairs


def fetch_by_user(token: str, userid: str) -> list[dict[str, Any]]:
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
            out.append({"follow_userid": userid, **item})
        cursor = (d.get("next_cursor") or "").strip()
        if not cursor:
            break
        time.sleep(0.03)
    return out


def flatten(item: dict[str, Any]) -> dict[str, Any]:
    ec = item.get("external_contact") or {}
    fi = item.get("follow_info") or {}
    mobiles = fi.get("remark_mobiles") or []
    channels = fi.get("wechat_channels")
    return {
        "follow_userid": item.get("follow_userid") or fi.get("userid"),
        "external_userid": ec.get("external_userid"),
        # external_contact
        "name": ec.get("name"),
        "position": ec.get("position"),
        "avatar": ec.get("avatar"),
        "corp_name": ec.get("corp_name"),
        "corp_full_name": ec.get("corp_full_name"),
        "type": ec.get("type"),
        "gender": ec.get("gender"),
        "unionid": ec.get("unionid"),
        "external_profile_json": json.dumps(ec.get("external_profile"), ensure_ascii=False)
        if ec.get("external_profile") is not None
        else None,
        # follow_info（官方示例完整字段）
        "remark": fi.get("remark"),
        "description": fi.get("description"),
        "createtime": fi.get("createtime"),
        "tag_id_json": json.dumps(fi.get("tag_id"), ensure_ascii=False) if fi.get("tag_id") is not None else None,
        "remark_corp_name": fi.get("remark_corp_name"),
        "remark_mobiles_json": json.dumps(mobiles, ensure_ascii=False) if mobiles else None,
        "remark_mobiles": ",".join(str(x) for x in mobiles) if mobiles else None,
        "oper_userid": fi.get("oper_userid"),
        "add_way": fi.get("add_way"),
        "state": fi.get("state"),
        "wechat_channels_nickname": (channels or {}).get("nickname") if isinstance(channels, dict) else None,
        "wechat_channels_source": (channels or {}).get("source") if isinstance(channels, dict) else None,
        "wechat_channels_json": json.dumps(channels, ensure_ascii=False) if channels is not None else None,
        "external_contact_json": json.dumps(ec, ensure_ascii=False),
        "follow_info_json": json.dumps(fi, ensure_ascii=False),
    }


def write_sql(path: Path, rows: list[dict[str, Any]]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ddl = f"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS {TABLE};
CREATE TABLE {TABLE} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NOT NULL,
  external_userid VARCHAR(64) NOT NULL,
  name VARCHAR(128) NULL,
  position VARCHAR(128) NULL,
  avatar VARCHAR(512) NULL,
  corp_name VARCHAR(128) NULL,
  corp_full_name VARCHAR(255) NULL,
  type TINYINT NULL COMMENT '1微信 2企微',
  gender TINYINT NULL,
  unionid VARCHAR(64) NULL,
  external_profile_json MEDIUMTEXT NULL,
  remark VARCHAR(255) NULL,
  description VARCHAR(512) NULL,
  createtime INT UNSIGNED NULL,
  tag_id_json TEXT NULL,
  remark_corp_name VARCHAR(128) NULL,
  remark_mobiles VARCHAR(512) NULL COMMENT '备注手机号逗号分隔',
  remark_mobiles_json TEXT NULL,
  oper_userid VARCHAR(64) NULL,
  add_way INT NULL,
  state VARCHAR(128) NULL COMMENT 'state企业自定义渠道值',
  wechat_channels_nickname VARCHAR(128) NULL,
  wechat_channels_source INT NULL,
  wechat_channels_json TEXT NULL,
  external_contact_json MEDIUMTEXT NULL,
  follow_info_json MEDIUMTEXT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_follow_ext (follow_userid, external_userid),
  KEY idx_name (name),
  KEY idx_createtime (createtime),
  KEY idx_mobiles (remark_mobiles(64))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='batch/get_by_user完整字段样例(今天N人)';
"""
    cols = (
        "follow_userid,external_userid,name,position,avatar,corp_name,corp_full_name,"
        "type,gender,unionid,external_profile_json,remark,description,createtime,"
        "tag_id_json,remark_corp_name,remark_mobiles,remark_mobiles_json,oper_userid,"
        "add_way,state,wechat_channels_nickname,wechat_channels_source,wechat_channels_json,"
        "external_contact_json,follow_info_json,fetched_at"
    )
    with path.open("w", encoding="utf-8") as f:
        f.write("-- full fields sample; does NOT touch served_* or qywx_external_contact_batch\n")
        f.write(ddl)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        for i in range(0, len(rows), 50):
            chunk = rows[i : i + 50]
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
                            _esc(r.get("position")),
                            _esc(r.get("avatar")),
                            _esc(r.get("corp_name")),
                            _esc(r.get("corp_full_name")),
                            _esc(r.get("type")),
                            _esc(r.get("gender")),
                            _esc(r.get("unionid")),
                            _esc(r.get("external_profile_json")),
                            _esc(r.get("remark")),
                            _esc(r.get("description")),
                            _esc(r.get("createtime")),
                            _esc(r.get("tag_id_json")),
                            _esc(r.get("remark_corp_name")),
                            _esc(r.get("remark_mobiles")),
                            _esc(r.get("remark_mobiles_json")),
                            _esc(r.get("oper_userid")),
                            _esc(r.get("add_way")),
                            _esc(r.get("state")),
                            _esc(r.get("wechat_channels_nickname")),
                            _esc(r.get("wechat_channels_source")),
                            _esc(r.get("wechat_channels_json")),
                            _esc(r.get("external_contact_json")),
                            _esc(r.get("follow_info_json")),
                            _esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                f.write(f"INSERT INTO {TABLE} ({cols}) VALUES\n")
                f.write(",\n".join(vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True)
    ap.add_argument("--people", type=int, default=10, help="今天活跃添加人数")
    ap.add_argument("--day", default="", help="YYYY-MM-DD，默认今天")
    args = ap.parse_args()

    day = datetime.strptime(args.day, "%Y-%m-%d") if args.day else datetime.now()
    follow_ids, today_pairs = today_scope(Path(args.from_json), args.people, day)
    if not follow_ids:
        raise RuntimeError("今天没有可拉取的 follow_userid")

    token = get_token()
    flats: list[dict[str, Any]] = []
    for i, uid in enumerate(follow_ids, 1):
        items = fetch_by_user(token, uid)
        kept = 0
        for it in items:
            row = flatten(it)
            eid = (row.get("external_userid") or "").strip()
            # 只保留「今天明细里出现过」的员工-客户对，避免拉全历史
            if (uid, eid) not in today_pairs:
                continue
            flats.append(row)
            kept += 1
        print(
            f"  {i}/{len(follow_ids)} {uid}: api={len(items)} 今日保留={kept} 累计 {len(flats)}",
            flush=True,
        )
        time.sleep(0.05)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = ROOT / "docs" / "export"
    out_sql = out_dir / f"qywx_external_full_today{args.people}_{stamp}.sql"
    out_json = out_dir / f"qywx_external_full_today{args.people}_{stamp}.json"
    write_sql(out_sql, flats)
    out_json.write_text(
        json.dumps(
            {"table": TABLE, "follow_ids": follow_ids, "count": len(flats), "rows": flats},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def nz(key: str) -> int:
        return sum(1 for r in flats if r.get(key) not in (None, "", []))

    print(f"完成 {len(flats)} 条 -> {out_sql.name} ({out_sql.stat().st_size // 1024} KB)", flush=True)
    print(
        "非空统计: "
        f"name={nz('name')} remark={nz('remark')} description={nz('description')} "
        f"remark_mobiles={nz('remark_mobiles')} state={nz('state')} "
        f"unionid={nz('unionid')} tag_id={nz('tag_id_json')} "
        f"wechat_channels={nz('wechat_channels_json')} external_profile={nz('external_profile_json')}",
        flush=True,
    )
    print(
        f"导入（只建 {TABLE}）:\n"
        f"  mysql ... db_fz_jingnao < {out_sql.name}\n"
        "查询:\n"
        f"  SELECT name, remark, remark_mobiles, description, state, add_way, "
        f"FROM_UNIXTIME(createtime) AS added_at FROM {TABLE} LIMIT 20;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
