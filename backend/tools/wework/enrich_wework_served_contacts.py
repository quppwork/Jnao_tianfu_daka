#!/usr/bin/env python3
"""为已服务的外部联系人补全：外部联系人姓名、添加人姓名、群名。

依赖本地缓存 JSON（由 sync_wework_served_contacts.py 生成），调用：
  - user/get                         → 添加人姓名
  - externalcontact/batch/get_by_user → 客户姓名
  - externalcontact/get              → 补漏客户姓名
  - externalcontact/groupchat/get    → 群名

输出：
  - docs/export/qywx_served_contacts_<batch>_enriched.json
  - docs/export/qywx_served_contacts_<batch>_enriched.sql  （上传服务器导入）

用法:
  python backend/tools/enrich_wework_served_contacts.py --from-json docs/export/qywx_served_contacts_XXXX.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


def _log(msg: str) -> None:
    print(msg, flush=True)

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

load_dotenv(BACKEND / ".env", override=False)
load_dotenv(ROOT / ".env", override=False)

QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


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
    return data["access_token"]


def fetch_follow_names(token: str, userids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    errors = 0
    for i, uid in enumerate(userids, 1):
        resp = requests.get(
            f"{QYAPI}/user/get",
            params={"access_token": token, "userid": uid},
            timeout=30,
        )
        data = resp.json()
        if data.get("errcode", 0) == 0 and data.get("name"):
            result[uid] = str(data["name"])
        else:
            errors += 1
            if errors <= 5:
                _log(f"  [warn] user/get {uid}: {data.get('errcode')} {data.get('errmsg')}")
        if i % 20 == 0 or i == len(userids):
            _log(f"  添加人姓名 {i}/{len(userids)}，成功 {len(result)}")
        time.sleep(0.05)
    return result


def fetch_external_names_by_followers(token: str, follow_userids: list[str]) -> dict[str, str]:
    """按添加人批量拉客户详情，得到 external_userid -> name。"""
    result: dict[str, str] = {}
    for i, uid in enumerate(follow_userids, 1):
        cursor = ""
        page = 0
        while True:
            page += 1
            payload: dict[str, Any] = {"userid_list": [uid], "limit": 100}
            if cursor:
                payload["cursor"] = cursor
            resp = requests.post(
                f"{QYAPI}/externalcontact/batch/get_by_user",
                params={"access_token": token},
                json=payload,
                timeout=60,
            )
            data = resp.json()
            if data.get("errcode", 0) != 0:
                print(f"  [warn] batch/get_by_user {uid}: {data.get('errcode')} {data.get('errmsg')}")
                break
            for item in data.get("external_contact_list") or []:
                ec = item.get("external_contact") or {}
                eid = (ec.get("external_userid") or "").strip()
                name = (ec.get("name") or "").strip()
                if eid and name:
                    result[eid] = name
            cursor = (data.get("next_cursor") or "").strip()
            if not cursor:
                break
            time.sleep(0.03)
        if i % 5 == 0 or i == len(follow_userids):
            print(f"  客户姓名进度 员工 {i}/{len(follow_userids)}，已映射 {len(result)}")
        time.sleep(0.05)
    return result


def fetch_external_names_by_ids(token: str, external_userids: list[str]) -> dict[str, str]:
    """对仍缺失的 external_userid 逐个 get。"""
    result: dict[str, str] = {}
    for i, eid in enumerate(external_userids, 1):
        resp = requests.get(
            f"{QYAPI}/externalcontact/get",
            params={"access_token": token, "external_userid": eid},
            timeout=30,
        )
        data = resp.json()
        if data.get("errcode", 0) == 0:
            name = ((data.get("external_contact") or {}).get("name") or "").strip()
            if name:
                result[eid] = name
        elif i <= 5:
            print(f"  [warn] externalcontact/get: {data.get('errcode')} {data.get('errmsg')}")
        if i % 100 == 0 or i == len(external_userids):
            print(f"  补漏客户姓名 {i}/{len(external_userids)}，成功 {len(result)}")
        time.sleep(0.05)
    return result


def fetch_chat_names(token: str, chat_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for i, cid in enumerate(chat_ids, 1):
        resp = requests.post(
            f"{QYAPI}/externalcontact/groupchat/get",
            params={"access_token": token},
            json={"chat_id": cid, "need_name": 0},
            timeout=30,
        )
        data = resp.json()
        if data.get("errcode", 0) == 0:
            name = ((data.get("group_chat") or {}).get("name") or "").strip()
            if name:
                result[cid] = name
        elif i <= 5:
            print(f"  [warn] groupchat/get: {data.get('errcode')} {data.get('errmsg')}")
        if i % 50 == 0 or i == len(chat_ids):
            print(f"  群名 {i}/{len(chat_ids)}，成功 {len(result)}")
        time.sleep(0.05)
    return result


def _ts_to_dt(ts: Any) -> str | None:
    if ts is None or ts == "":
        return None
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return None


def _esc(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(int(v))
    s = str(v).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def write_enriched_sql(
    path: Path,
    *,
    batch_id: str,
    rows: list[dict[str, Any]],
    stats: list[dict[str, Any]],
) -> None:
    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ddl = """
CREATE TABLE IF NOT EXISTS qywx_served_external_contact (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sync_batch_id VARCHAR(32) NOT NULL,
  tmp_openid VARCHAR(128) NOT NULL DEFAULT '',
  external_userid VARCHAR(64) NULL,
  is_customer TINYINT(1) NOT NULL DEFAULT 0,
  name VARCHAR(128) NULL COMMENT '外部联系人姓名',
  follow_userid VARCHAR(64) NULL,
  follow_name VARCHAR(128) NULL COMMENT '添加人姓名',
  chat_id VARCHAR(64) NULL,
  chat_name VARCHAR(255) NULL COMMENT '外部群名',
  add_time INT UNSIGNED NULL,
  add_time_dt DATETIME NULL,
  synced_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_batch (sync_batch_id),
  KEY idx_follow (follow_userid),
  KEY idx_external (external_userid),
  KEY idx_follow_name (follow_name),
  KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信已服务的外部联系人明细(含姓名)';

CREATE TABLE IF NOT EXISTS qywx_served_external_contact_stat (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sync_batch_id VARCHAR(32) NOT NULL,
  follow_userid VARCHAR(64) NOT NULL,
  follow_name VARCHAR(128) NULL COMMENT '添加人姓名',
  contact_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  customer_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  other_cnt INT UNSIGNED NOT NULL DEFAULT 0,
  synced_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_follow (sync_batch_id, follow_userid),
  KEY idx_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企业微信已服务外部联系人-按添加人汇总';
"""
    with path.open("w", encoding="utf-8") as f:
        f.write("-- enriched qywx served external contacts\n")
        f.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
        f.write("DROP TABLE IF EXISTS qywx_served_external_contact;\n")
        f.write("DROP TABLE IF EXISTS qywx_served_external_contact_stat;\n")
        f.write(ddl)
        batch_size = 400
        cols = (
            "sync_batch_id,tmp_openid,external_userid,is_customer,name,"
            "follow_userid,follow_name,chat_id,chat_name,add_time,add_time_dt,synced_at"
        )
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
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
                            "1" if r.get("is_customer") else "0",
                            _esc(r.get("name")),
                            _esc(r.get("follow_userid")),
                            _esc(r.get("follow_name")),
                            _esc(r.get("chat_id")),
                            _esc(r.get("chat_name")),
                            _esc(at_i),
                            _esc(_ts_to_dt(at_i)),
                            _esc(synced_at),
                        ]
                    )
                    + ")"
                )
            f.write(f"INSERT INTO qywx_served_external_contact ({cols}) VALUES\n")
            f.write(",\n".join(vals))
            f.write(";\n")
        if stats:
            scols = "sync_batch_id,follow_userid,follow_name,contact_cnt,customer_cnt,other_cnt,synced_at"
            vals = [
                "("
                + ",".join(
                    [
                        _esc(batch_id),
                        _esc(s.get("follow_userid")),
                        _esc(s.get("follow_name")),
                        _esc(s.get("contact_cnt")),
                        _esc(s.get("customer_cnt")),
                        _esc(s.get("other_cnt")),
                        _esc(synced_at),
                    ]
                )
                + ")"
                for s in stats
            ]
            f.write(f"INSERT INTO qywx_served_external_contact_stat ({scols}) VALUES\n")
            f.write(",\n".join(vals))
            f.write(";\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="补全已服务外部联系人姓名字段")
    parser.add_argument("--from-json", required=True, help="sync 脚本生成的缓存 JSON")
    parser.add_argument("--skip-chat", action="store_true", help="跳过群名拉取（更快）")
    parser.add_argument("--skip-external-get", action="store_true", help="跳过逐个补漏客户详情")
    args = parser.parse_args()

    src = Path(args.from_json)
    data = json.loads(src.read_text(encoding="utf-8"))
    batch_id = str(data.get("batch_id") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    rows: list[dict[str, Any]] = list(data.get("rows") or [])
    stats: list[dict[str, Any]] = list(data.get("stats") or [])

    follow_ids = sorted({(r.get("follow_userid") or "").strip() for r in rows if r.get("follow_userid")})
    external_ids = sorted({(r.get("external_userid") or "").strip() for r in rows if r.get("external_userid")})
    chat_ids = sorted({(r.get("chat_id") or "").strip() for r in rows if r.get("chat_id")})

    print(f"源数据: rows={len(rows)} follow={len(follow_ids)} external={len(external_ids)} chat={len(chat_ids)}")

    token = get_access_token(_require_env("WEWORK_CORPID"), _require_env("WEWORK_CORPSECRET"))

    print("1) 拉取添加人姓名 user/get ...")
    follow_names = fetch_follow_names(token, follow_ids)

    print("2) 按添加人批量拉取客户姓名 batch/get_by_user ...")
    external_names = fetch_external_names_by_followers(token, follow_ids)

    missing_ext = [e for e in external_ids if e not in external_names]
    if missing_ext and not args.skip_external_get:
        print(f"3) 补漏客户姓名 externalcontact/get，剩余 {len(missing_ext)} ...")
        # 控制补漏上限，避免过久；可多次跑
        external_names.update(fetch_external_names_by_ids(token, missing_ext))
    else:
        print(f"3) 跳过补漏（缺失 {len(missing_ext)}）")

    chat_names: dict[str, str] = {}
    if not args.skip_chat and chat_ids:
        print("4) 拉取群名 groupchat/get ...")
        chat_names = fetch_chat_names(token, chat_ids)
    else:
        print("4) 跳过群名")

    for r in rows:
        eid = (r.get("external_userid") or "").strip()
        fid = (r.get("follow_userid") or "").strip()
        cid = (r.get("chat_id") or "").strip()
        if eid and eid in external_names:
            r["name"] = external_names[eid]
        if fid and fid in follow_names:
            r["follow_name"] = follow_names[fid]
        if cid and cid in chat_names:
            r["chat_name"] = chat_names[cid]

    for s in stats:
        fid = (s.get("follow_userid") or "").strip()
        if fid in follow_names:
            s["follow_name"] = follow_names[fid]

    named_ext = sum(1 for r in rows if r.get("name"))
    named_follow = sum(1 for r in rows if r.get("follow_name"))
    named_chat = sum(1 for r in rows if r.get("chat_name"))
    print(
        f"补全结果: 有外部姓名行 {named_ext}/{len(rows)}, "
        f"有添加人姓名行 {named_follow}/{len(rows)}, 有群名行 {named_chat}/{len(rows)}"
    )
    print(f"映射规模: follow_names={len(follow_names)} external_names={len(external_names)} chat_names={len(chat_names)}")

    out_json = src.with_name(src.stem + "_enriched.json")
    out_sql = src.with_name(src.stem + "_enriched.sql")
    payload = {
        "batch_id": batch_id,
        "enriched_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": len(rows),
        "follow_name_map": follow_names,
        "external_name_count": len(external_names),
        "chat_name_count": len(chat_names),
        "rows": rows,
        "stats": stats,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    write_enriched_sql(out_sql, batch_id=batch_id, rows=rows, stats=stats)
    print(f"已写 {out_json}")
    print(f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)")
    print("请上传 enriched.sql 到服务器后执行 mysql 导入（会重建两张表）。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
