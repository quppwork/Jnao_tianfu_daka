#!/usr/bin/env python3
"""基于已有 external_userid，调用 externalcontact/get 拉取客户详情。

官方:
  GET https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get
      ?access_token=ACCESS_TOKEN&external_userid=EXTERNAL_USERID&cursor=CURSOR

用法:
  python -u backend/tools/fetch_wework_external_get.py --from-json docs/export/xxx_plan_a_7d_enriched.json
  python -u backend/tools/fetch_wework_external_get.py --from-json docs/export/qywx_served_contacts_XXXX.json --since-days 7
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
        raise RuntimeError(f"gettoken 失败: {d}")
    return d["access_token"]


def collect_external_ids(path: Path, since_days: int) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = list(data.get("rows") or [])
    if since_days > 0:
        cut = int((datetime.now() - timedelta(days=since_days)).timestamp())
        rows = [r for r in rows if (r.get("add_time") or 0) >= cut]
    ids = sorted({(r.get("external_userid") or "").strip() for r in rows if r.get("external_userid")})
    return ids


def fetch_one(token: str, external_userid: str) -> dict[str, Any]:
    """拉全部分页 follow_user，合并为一条详情。"""
    cursor = ""
    merged: dict[str, Any] = {"external_userid": external_userid, "errcode": 0}
    follow_users: list[dict[str, Any]] = []
    while True:
        params = {"access_token": token, "external_userid": external_userid}
        if cursor:
            params["cursor"] = cursor
        d = requests.get(f"{QYAPI}/externalcontact/get", params=params, timeout=30).json()
        err = d.get("errcode", 0)
        if err != 0:
            return {
                "external_userid": external_userid,
                "errcode": err,
                "errmsg": d.get("errmsg"),
                "external_contact": None,
                "follow_user": [],
            }
        if not merged.get("external_contact"):
            merged["external_contact"] = d.get("external_contact")
        follow_users.extend(d.get("follow_user") or [])
        cursor = (d.get("next_cursor") or "").strip()
        if not cursor:
            break
        time.sleep(0.03)
    merged["follow_user"] = follow_users
    return merged


def flatten_row(detail: dict[str, Any]) -> dict[str, Any]:
    ec = detail.get("external_contact") or {}
    follows = detail.get("follow_user") or []
    # 跟进人 userid 列表、最早添加时间
    follow_userids = []
    createtimes = []
    for f in follows:
        uid = (f.get("userid") or "").strip()
        if uid:
            follow_userids.append(uid)
        if f.get("createtime") is not None:
            try:
                createtimes.append(int(f["createtime"]))
            except (TypeError, ValueError):
                pass
    return {
        "external_userid": detail.get("external_userid") or ec.get("external_userid"),
        "errcode": detail.get("errcode", 0),
        "errmsg": detail.get("errmsg"),
        "name": ec.get("name"),
        "avatar": ec.get("avatar"),
        "type": ec.get("type"),
        "gender": ec.get("gender"),
        "unionid": ec.get("unionid"),
        "position": ec.get("position"),
        "corp_name": ec.get("corp_name"),
        "corp_full_name": ec.get("corp_full_name"),
        "external_profile_json": json.dumps(ec.get("external_profile"), ensure_ascii=False)
        if ec.get("external_profile")
        else None,
        "follow_user_count": len(follows),
        "follow_userids": ",".join(follow_userids) if follow_userids else None,
        "first_follow_time": min(createtimes) if createtimes else None,
        "follow_user_json": json.dumps(follows, ensure_ascii=False) if follows else None,
        "raw_json": json.dumps(
            {"external_contact": ec, "follow_user": follows},
            ensure_ascii=False,
        )
        if ec or follows
        else None,
    }


def write_sql(path: Path, flats: list[dict[str, Any]]) -> None:
    ddl = r"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS qywx_external_contact_detail;
CREATE TABLE qywx_external_contact_detail (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  external_userid VARCHAR(64) NOT NULL,
  errcode INT NOT NULL DEFAULT 0,
  errmsg VARCHAR(255) NULL,
  name VARCHAR(128) NULL,
  avatar VARCHAR(512) NULL,
  type TINYINT NULL COMMENT '1微信 2企业微信',
  gender TINYINT NULL COMMENT '0未知 1男 2女',
  unionid VARCHAR(64) NULL,
  position VARCHAR(128) NULL,
  corp_name VARCHAR(128) NULL,
  corp_full_name VARCHAR(255) NULL,
  external_profile_json MEDIUMTEXT NULL,
  follow_user_count INT UNSIGNED NOT NULL DEFAULT 0,
  follow_userids TEXT NULL COMMENT '跟进人userid逗号分隔',
  first_follow_time INT UNSIGNED NULL,
  follow_user_json MEDIUMTEXT NULL COMMENT 'follow_user原样JSON',
  raw_json MEDIUMTEXT NULL COMMENT '接口主要返回原样',
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_external (external_userid),
  KEY idx_name (name),
  KEY idx_errcode (errcode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='externalcontact/get 客户详情';
"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("w", encoding="utf-8") as f:
        f.write("-- from externalcontact/get\n")
        f.write(ddl)
        ok = [x for x in flats if x.get("errcode", 0) == 0 and x.get("name") is not None]
        # 成功+失败都落库，便于排查
        for i in range(0, len(flats), 100):
            chunk = flats[i : i + 100]
            vals = []
            for r in chunk:
                vals.append(
                    "("
                    + ",".join(
                        [
                            _esc(r.get("external_userid")),
                            _esc(r.get("errcode") or 0),
                            _esc(r.get("errmsg")),
                            _esc(r.get("name")),
                            _esc(r.get("avatar")),
                            _esc(r.get("type")),
                            _esc(r.get("gender")),
                            _esc(r.get("unionid")),
                            _esc(r.get("position")),
                            _esc(r.get("corp_name")),
                            _esc(r.get("corp_full_name")),
                            _esc(r.get("external_profile_json")),
                            _esc(r.get("follow_user_count") or 0),
                            _esc(r.get("follow_userids")),
                            _esc(r.get("first_follow_time")),
                            _esc(r.get("follow_user_json")),
                            _esc(r.get("raw_json")),
                            _esc(now),
                        ]
                    )
                    + ")"
                )
            f.write(
                "INSERT INTO qywx_external_contact_detail ("
                "external_userid,errcode,errmsg,name,avatar,type,gender,unionid,"
                "position,corp_name,corp_full_name,external_profile_json,"
                "follow_user_count,follow_userids,first_follow_time,"
                "follow_user_json,raw_json,fetched_at"
                ") VALUES\n"
            )
            f.write(",\n".join(vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")
        f.write(f"-- ok_with_name={len(ok)} total={len(flats)}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True, help="含 rows[].external_userid 的缓存")
    ap.add_argument("--since-days", type=int, default=0, help="按 add_time 过滤后再取 userid；enriched json 可设 0")
    ap.add_argument("--limit", type=int, default=0, help="最多拉多少个，0=全部")
    ap.add_argument("--sleep", type=float, default=0.05)
    args = ap.parse_args()

    src = Path(args.from_json)
    ids = collect_external_ids(src, args.since_days)
    if args.limit > 0:
        ids = ids[: args.limit]
    print(f"待拉取 external_userid: {len(ids)}", flush=True)

    token = get_token()
    details: list[dict[str, Any]] = []
    flats: list[dict[str, Any]] = []
    ok = fail = 0
    for i, eid in enumerate(ids, 1):
        detail = fetch_one(token, eid)
        details.append(detail)
        flat = flatten_row(detail)
        flats.append(flat)
        if flat.get("errcode", 0) == 0 and flat.get("name"):
            ok += 1
        else:
            fail += 1
            if fail <= 8:
                print(f"  [fail] {eid}: {flat.get('errcode')} {flat.get('errmsg')}", flush=True)
        if i % 20 == 0 or i == len(ids):
            print(f"  progress {i}/{len(ids)} ok={ok} fail={fail}", flush=True)
        time.sleep(args.sleep)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_json = ROOT / "docs" / "export" / f"qywx_external_get_{stamp}.json"
    out_sql = ROOT / "docs" / "export" / f"qywx_external_get_{stamp}.sql"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps({"count": len(details), "ok": ok, "fail": fail, "items": details}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_sql(out_sql, flats)
    print(f"完成 ok={ok} fail={fail}", flush=True)
    print(f"已写 {out_json}", flush=True)
    print(f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)", flush=True)
    print(
        "导入:\n"
        f"  mysql ... db_fz_jingnao < {out_sql.name}\n"
        "查询:\n"
        "  SELECT name, type, gender, follow_user_count, follow_userids\n"
        "  FROM qywx_external_contact_detail WHERE errcode=0 LIMIT 20;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
