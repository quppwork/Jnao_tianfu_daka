#!/usr/bin/env python3
"""企业成员 userid -> 微信 openid（user/convert_to_openid），先转 N 条。

POST /cgi-bin/user/convert_to_openid
场景：企业支付（红包/向员工付款）等。
注：成员需用微信登录企微或关注微信插件；外部联系人请用 externalcontact/convert_to_openid。

用法:
  python -u backend/tools/fetch_wework_user_convert_openid.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
TABLE = "qywx_user_openid_map"


def _env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise RuntimeError(f"缺少 {name}")
    return v


def _esc(v: Any) -> str:
    if v is None:
        return "NULL"
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


def pick_userids(limit: int) -> list[str]:
    """优先收款 payee_userid，不足再从 7 日已服务员工补。"""
    export = ROOT / "docs" / "export"
    ids: list[str] = []
    seen: set[str] = set()

    def add(uid: str) -> None:
        uid = (uid or "").strip()
        if not uid or uid in seen:
            return
        # 外部联系人 wm/wo 不是成员 userid
        if uid.startswith(("wm", "wo", "wb")):
            return
        seen.add(uid)
        ids.append(uid)

    for p in sorted(export.glob("qywx_externalpay_*.json")):
        for b in json.loads(p.read_text(encoding="utf-8")).get("bill_list") or []:
            add(b.get("payee_userid") or "")
            if len(ids) >= limit:
                return ids

    for p in sorted(export.glob("*plan_a_7d_enriched.json")) + sorted(
        export.glob("qywx_served_contacts_*_enriched.json")
    ):
        data = json.loads(p.read_text(encoding="utf-8"))
        for s in data.get("stats") or []:
            add(s.get("follow_userid") or "")
            if len(ids) >= limit:
                return ids
        for r in data.get("rows") or []:
            add(r.get("follow_userid") or "")
            if len(ids) >= limit:
                return ids

    return ids[:limit]


def convert_one(token: str, userid: str) -> dict[str, Any]:
    d = requests.post(
        f"{QYAPI}/user/convert_to_openid",
        params={"access_token": token},
        json={"userid": userid},
        timeout=30,
    ).json()
    return {
        "userid": userid,
        "openid": d.get("openid"),
        "errcode": d.get("errcode", 0),
        "errmsg": d.get("errmsg"),
    }


def name_lookup(token: str, userid: str) -> str | None:
    export = ROOT / "docs" / "export"
    for p in sorted(export.glob("*enriched.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for s in data.get("stats") or []:
            if s.get("follow_userid") == userid and s.get("follow_name"):
                return s.get("follow_name")
        for r in data.get("rows") or []:
            if r.get("follow_userid") == userid and r.get("follow_name"):
                return r.get("follow_name")
    d = requests.get(
        f"{QYAPI}/user/get",
        params={"access_token": token, "userid": userid},
        timeout=30,
    ).json()
    if d.get("errcode", 0) == 0:
        return d.get("name")
    return None


def write_sql(path: Path, rows: list[dict[str, Any]]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ddl = f"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS {TABLE};
CREATE TABLE {TABLE} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  userid VARCHAR(64) NOT NULL COMMENT '企业成员userid',
  name VARCHAR(128) NULL,
  openid VARCHAR(64) NULL COMMENT '微信openid',
  errcode INT NOT NULL DEFAULT 0,
  errmsg VARCHAR(255) NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_userid (userid),
  KEY idx_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成员userid转微信openid样例';
"""
    with path.open("w", encoding="utf-8") as f:
        f.write("-- user/convert_to_openid sample; own table only\n")
        f.write(ddl)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        vals = []
        for r in rows:
            vals.append(
                "("
                + ",".join(
                    [
                        _esc(r.get("userid")),
                        _esc(r.get("name")),
                        _esc(r.get("openid")),
                        _esc(r.get("errcode") or 0),
                        _esc(r.get("errmsg")),
                        _esc(now),
                    ]
                )
                + ")"
            )
        if vals:
            f.write(
                f"INSERT INTO {TABLE} "
                "(userid,name,openid,errcode,errmsg,fetched_at) VALUES\n"
            )
            f.write(",\n".join(vals) + ";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    ids = pick_userids(args.limit)
    print(f"待转换 {len(ids)} 个成员 userid", flush=True)
    for i, uid in enumerate(ids, 1):
        print(f"  {i}. {uid}", flush=True)

    token = get_token()
    rows: list[dict[str, Any]] = []
    ok = 0
    for i, uid in enumerate(ids, 1):
        r = convert_one(token, uid)
        r["name"] = name_lookup(token, uid)
        rows.append(r)
        if r.get("errcode", 0) == 0 and r.get("openid"):
            ok += 1
            print(f"  ok {i}/{len(ids)} {r.get('name') or uid} -> {r.get('openid')}", flush=True)
        else:
            print(
                f"  fail {i}/{len(ids)} {uid}: {r.get('errcode')} {r.get('errmsg')}",
                flush=True,
            )
        time.sleep(0.05)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = ROOT / "docs" / "export"
    out_sql = out_dir / f"qywx_user_openid_map_{args.limit}_{stamp}.sql"
    out_json = out_dir / f"qywx_user_openid_map_{args.limit}_{stamp}.json"
    write_sql(out_sql, rows)
    out_json.write_text(
        json.dumps({"count": len(rows), "ok": ok, "rows": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"完成 ok={ok}/{len(rows)}", flush=True)
    print(f"已写 {out_sql}", flush=True)
    print(f"导入表 {TABLE}（不覆盖其它表）", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
