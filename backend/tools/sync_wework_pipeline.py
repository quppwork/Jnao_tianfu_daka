#!/usr/bin/env python3
"""企业微信关联数据一站式同步：先近 N 天，再增量补历史。

流程:
  1) 拉已服务外部联系人 contact_list → 本地缓存
  2) 近 N 天：客户详情(unionid) + 标签库 + 跟进人关系 + 对外收款
  3) 增量历史：对尚未同步详情的客户分批补 get
  4) 生成收款 enrich SQL（unionid → third_uid / xet_user_id / bind_phone）

默认只写 docs/export/*.sql，不改库。加 --apply 才写库。
进度记在 docs/export/.qywx_pipeline_state.json，可断点续跑。

用法:
  # 近7天 + 历史每批200人（可多次跑直到补完）
  python -u backend/tools/sync_wework_pipeline.py --recent-days 7 --history-batch 200

  # 只用外网 RDS 主机（本机）
  python -u backend/tools/sync_wework_pipeline.py --db-host rm-xxxno.mysql.rds.aliyuncs.com --apply

  # 只跑近7天 / 只补历史 / 只生成 enrich
  python -u backend/tools/sync_wework_pipeline.py --recent-only
  python -u backend/tools/sync_wework_pipeline.py --history-only --history-batch 300
  python -u backend/tools/sync_wework_pipeline.py --enrich-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from _wework_paths import export_dir, load_env, project_roots  # noqa: E402

BACKEND, ROOT = project_roots(__file__)
load_env(BACKEND, ROOT)
EXPORT = export_dir(BACKEND, ROOT)
EXPORT.mkdir(parents=True, exist_ok=True)

import sync_wework_week_contacts as week  # noqa: E402
import fetch_wework_externalpay_bills as pay  # noqa: E402

QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"
STATE_PATH = EXPORT / ".qywx_pipeline_state.json"
PAY_TABLE = "qywx_pay_bill"


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "synced_external_userids": [],
        "failed_external_userids": {},
        "pay_synced_ranges": [],
        "updated_at": None,
    }


def save_state(state: dict[str, Any]) -> None:
    EXPORT.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_token() -> str:
    return week.get_token()


def fetch_contact_list(token: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = ""
    page = 0
    while True:
        page += 1
        body: dict[str, Any] = {"limit": 1000}
        if cursor:
            body["cursor"] = cursor
        d = requests.post(
            f"{QYAPI}/externalcontact/contact_list",
            params={"access_token": token},
            json=body,
            timeout=60,
        ).json()
        if d.get("errcode", 0) != 0:
            raise RuntimeError(f"contact_list 失败 page={page}: {d}")
        chunk = d.get("contact_list") or []
        rows.extend(chunk)
        _log(f"  contact_list page {page}: +{len(chunk)} 累计 {len(rows)}")
        cursor = (d.get("next_cursor") or "").strip()
        if not cursor:
            break
        time.sleep(0.05)
    return rows


def save_served_cache(rows: list[dict[str, Any]]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    path = EXPORT / f"qywx_served_contacts_{stamp}.json"
    path.write_text(
        json.dumps({"rows": rows, "count": len(rows), "fetched_at": stamp}, ensure_ascii=False),
        encoding="utf-8",
    )
    _log(f"已写缓存 {path.name} ({len(rows)} 行)")
    return path


def all_external_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        eid = (r.get("external_userid") or "").strip()
        if eid and eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out


def recent_scope(
    rows: list[dict[str, Any]], days: int
) -> tuple[list[str], set[tuple[str, str]], int]:
    since_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    pairs: set[tuple[str, str]] = set()
    eids: list[str] = []
    seen: set[str] = set()
    for r in rows:
        at = int(r.get("add_time") or 0)
        if at and at < since_ts:
            continue
        eid = (r.get("external_userid") or "").strip()
        fid = (r.get("follow_userid") or "").strip()
        if eid and eid not in seen:
            seen.add(eid)
            eids.append(eid)
        if eid and fid:
            pairs.add((fid, eid))
    return eids, pairs, since_ts


def process_details(
    token: str,
    eids: list[str],
    pairs: set[tuple[str, str]] | None,
    since_ts: int | None,
    tag_map: dict[str, dict[str, Any]],
    *,
    include_all_follows: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """拉取详情；pairs/since_ts 用于过滤 full/link；include_all_follows=True 则不过滤。"""
    details: list[dict[str, Any]] = []
    fulls: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    follow_ids: set[str] = set()
    for i, eid in enumerate(eids, 1):
        detail = week.fetch_one(token, eid)
        flat = week.flatten_detail(detail)
        details.append(flat)
        ec = detail.get("external_contact") or {}
        for fi in detail.get("follow_user") or []:
            fid = (fi.get("userid") or "").strip()
            if not fid:
                continue
            ct = int(fi.get("createtime") or 0)
            if include_all_follows:
                keep = True
            else:
                keep = (since_ts is not None and ct >= since_ts) or (
                    pairs is not None and (fid, eid) in pairs
                )
            if not keep:
                continue
            follow_ids.add(fid)
            fulls.append(week.flatten_full(ec, fi))
            tids = week.extract_tag_ids(fi)
            base = {
                "follow_userid": fid,
                "external_userid": eid,
                "name": ec.get("name"),
                "remark": fi.get("remark"),
                "createtime": fi.get("createtime"),
                "add_way": fi.get("add_way"),
                "state": fi.get("state"),
            }
            if not tids:
                links.append(
                    {
                        **base,
                        "tag_id": None,
                        "tag_name": None,
                        "group_id": None,
                        "group_name": None,
                    }
                )
            else:
                for tid in tids:
                    info = tag_map.get(tid) or {}
                    api_tag = next(
                        (
                            t
                            for t in (fi.get("tags") or [])
                            if isinstance(t, dict) and str(t.get("tag_id")) == tid
                        ),
                        {},
                    )
                    links.append(
                        {
                            **base,
                            "tag_id": tid,
                            "tag_name": info.get("tag_name") or api_tag.get("tag_name"),
                            "group_id": info.get("group_id") or api_tag.get("group_id"),
                            "group_name": info.get("group_name") or api_tag.get("group_name"),
                        }
                    )
        if i % 20 == 0 or i == len(eids):
            ok_u = sum(1 for d in details if d.get("unionid"))
            fail = sum(1 for d in details if d.get("errcode"))
            _log(f"  get {i}/{len(eids)} detail={len(details)} full={len(fulls)} unionid={ok_u} fail={fail}")
        time.sleep(0.04)
    return details, fulls, links, follow_ids


def write_upsert_sql(
    path: Path,
    *,
    details: list[dict[str, Any]],
    fulls: list[dict[str, Any]],
    tag_map: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    follows: dict[str, str],
    recreate_tags: bool,
) -> None:
    """增量友好：建表 IF NOT EXISTS + INSERT ON DUPLICATE KEY UPDATE。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("w", encoding="utf-8") as f:
        f.write("-- pipeline upsert; safe for incremental import\n")
        f.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
        f.write(
            """
CREATE TABLE IF NOT EXISTS qywx_external_contact_detail (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  external_userid VARCHAR(64) NOT NULL,
  errcode INT NOT NULL DEFAULT 0,
  errmsg VARCHAR(255) NULL,
  name VARCHAR(128) NULL,
  avatar VARCHAR(512) NULL,
  type TINYINT NULL,
  gender TINYINT NULL,
  unionid VARCHAR(64) NULL,
  position VARCHAR(128) NULL,
  corp_name VARCHAR(128) NULL,
  corp_full_name VARCHAR(255) NULL,
  external_profile_json MEDIUMTEXT NULL,
  follow_user_count INT UNSIGNED NOT NULL DEFAULT 0,
  follow_userids TEXT NULL,
  first_follow_time INT UNSIGNED NULL,
  follow_user_json MEDIUMTEXT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_external (external_userid),
  KEY idx_unionid (unionid),
  KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qywx_external_contact_full (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  follow_userid VARCHAR(64) NOT NULL,
  external_userid VARCHAR(64) NOT NULL,
  name VARCHAR(128) NULL,
  position VARCHAR(128) NULL,
  avatar VARCHAR(512) NULL,
  corp_name VARCHAR(128) NULL,
  corp_full_name VARCHAR(255) NULL,
  type TINYINT NULL,
  gender TINYINT NULL,
  unionid VARCHAR(64) NULL,
  external_profile_json MEDIUMTEXT NULL,
  remark VARCHAR(255) NULL,
  description VARCHAR(512) NULL,
  createtime INT UNSIGNED NULL,
  tag_id_json TEXT NULL,
  remark_corp_name VARCHAR(128) NULL,
  remark_mobiles VARCHAR(512) NULL,
  remark_mobiles_json TEXT NULL,
  oper_userid VARCHAR(64) NULL,
  add_way INT NULL,
  state VARCHAR(128) NULL,
  wechat_channels_nickname VARCHAR(128) NULL,
  wechat_channels_source INT NULL,
  wechat_channels_json TEXT NULL,
  external_contact_json MEDIUMTEXT NULL,
  follow_info_json MEDIUMTEXT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_follow_ext (follow_userid, external_userid),
  KEY idx_external (external_userid),
  KEY idx_unionid (unionid),
  KEY idx_createtime (createtime)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qywx_corp_tag (
  tag_id VARCHAR(64) NOT NULL,
  tag_name VARCHAR(128) NULL,
  group_id VARCHAR(64) NULL,
  group_name VARCHAR(128) NULL,
  tag_order INT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qywx_contact_tag_link (
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
  KEY idx_tag (tag_id),
  KEY idx_follow_ext_tag (follow_userid, external_userid, tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS qywx_follow_user (
  follow_userid VARCHAR(64) NOT NULL,
  follow_name VARCHAR(128) NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
        )

        if recreate_tags and tag_map:
            f.write("DELETE FROM qywx_corp_tag;\n")
            tag_vals = []
            for tid, info in tag_map.items():
                tag_vals.append(
                    "("
                    + ",".join(
                        [
                            week._esc(tid),
                            week._esc(info.get("tag_name")),
                            week._esc(info.get("group_id")),
                            week._esc(info.get("group_name")),
                            week._esc(info.get("order")),
                            week._esc(now),
                        ]
                    )
                    + ")"
                )
            for i in range(0, len(tag_vals), 100):
                f.write(
                    "INSERT INTO qywx_corp_tag "
                    "(tag_id,tag_name,group_id,group_name,tag_order,fetched_at) VALUES\n"
                )
                f.write(",\n".join(tag_vals[i : i + 100]) + ";\n")

        # detail upsert
        cols_d = (
            "external_userid,errcode,errmsg,name,avatar,type,gender,unionid,position,"
            "corp_name,corp_full_name,external_profile_json,follow_user_count,"
            "follow_userids,first_follow_time,follow_user_json,fetched_at"
        )
        for i in range(0, len(details), 40):
            vals = []
            for r in details[i : i + 40]:
                if not r.get("external_userid"):
                    continue
                vals.append(
                    "("
                    + ",".join(
                        [
                            week._esc(r.get("external_userid")),
                            week._esc(r.get("errcode") or 0),
                            week._esc(r.get("errmsg")),
                            week._esc(r.get("name")),
                            week._esc(r.get("avatar")),
                            week._esc(r.get("type")),
                            week._esc(r.get("gender")),
                            week._esc(r.get("unionid")),
                            week._esc(r.get("position")),
                            week._esc(r.get("corp_name")),
                            week._esc(r.get("corp_full_name")),
                            week._esc(r.get("external_profile_json")),
                            week._esc(r.get("follow_user_count") or 0),
                            week._esc(r.get("follow_userids")),
                            week._esc(r.get("first_follow_time")),
                            week._esc(r.get("follow_user_json")),
                            week._esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                f.write(f"INSERT INTO qywx_external_contact_detail ({cols_d}) VALUES\n")
                f.write(",\n".join(vals) + "\n")
                f.write(
                    "ON DUPLICATE KEY UPDATE "
                    "errcode=VALUES(errcode),errmsg=VALUES(errmsg),name=VALUES(name),"
                    "avatar=VALUES(avatar),type=VALUES(type),gender=VALUES(gender),"
                    "unionid=VALUES(unionid),position=VALUES(position),"
                    "corp_name=VALUES(corp_name),corp_full_name=VALUES(corp_full_name),"
                    "external_profile_json=VALUES(external_profile_json),"
                    "follow_user_count=VALUES(follow_user_count),"
                    "follow_userids=VALUES(follow_userids),"
                    "first_follow_time=VALUES(first_follow_time),"
                    "follow_user_json=VALUES(follow_user_json),"
                    "fetched_at=VALUES(fetched_at);\n"
                )

        cols_f = (
            "follow_userid,external_userid,name,position,avatar,corp_name,corp_full_name,"
            "type,gender,unionid,external_profile_json,remark,description,createtime,"
            "tag_id_json,remark_corp_name,remark_mobiles,remark_mobiles_json,oper_userid,"
            "add_way,state,wechat_channels_nickname,wechat_channels_source,wechat_channels_json,"
            "external_contact_json,follow_info_json,fetched_at"
        )
        for i in range(0, len(fulls), 30):
            vals = []
            eids_chunk = set()
            for r in fulls[i : i + 30]:
                if not r.get("external_userid") or not r.get("follow_userid"):
                    continue
                eids_chunk.add((r.get("follow_userid"), r.get("external_userid")))
                vals.append(
                    "("
                    + ",".join(
                        [
                            week._esc(r.get("follow_userid")),
                            week._esc(r.get("external_userid")),
                            week._esc(r.get("name")),
                            week._esc(r.get("position")),
                            week._esc(r.get("avatar")),
                            week._esc(r.get("corp_name")),
                            week._esc(r.get("corp_full_name")),
                            week._esc(r.get("type")),
                            week._esc(r.get("gender")),
                            week._esc(r.get("unionid")),
                            week._esc(r.get("external_profile_json")),
                            week._esc(r.get("remark")),
                            week._esc(r.get("description")),
                            week._esc(r.get("createtime")),
                            week._esc(r.get("tag_id_json")),
                            week._esc(r.get("remark_corp_name")),
                            week._esc(r.get("remark_mobiles")),
                            week._esc(r.get("remark_mobiles_json")),
                            week._esc(r.get("oper_userid")),
                            week._esc(r.get("add_way")),
                            week._esc(r.get("state")),
                            week._esc(r.get("wechat_channels_nickname")),
                            week._esc(r.get("wechat_channels_source")),
                            week._esc(r.get("wechat_channels_json")),
                            week._esc(r.get("external_contact_json")),
                            week._esc(r.get("follow_info_json")),
                            week._esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                # 先删本批关系，避免标签变化残留（按 follow+external）
                for fid, eid in eids_chunk:
                    f.write(
                        "DELETE FROM qywx_contact_tag_link WHERE "
                        f"follow_userid={week._esc(fid)} AND external_userid={week._esc(eid)};\n"
                    )
                f.write(f"INSERT INTO qywx_external_contact_full ({cols_f}) VALUES\n")
                f.write(",\n".join(vals) + "\n")
                f.write(
                    "ON DUPLICATE KEY UPDATE "
                    "name=VALUES(name),unionid=VALUES(unionid),remark=VALUES(remark),"
                    "description=VALUES(description),createtime=VALUES(createtime),"
                    "tag_id_json=VALUES(tag_id_json),remark_mobiles=VALUES(remark_mobiles),"
                    "add_way=VALUES(add_way),state=VALUES(state),"
                    "external_contact_json=VALUES(external_contact_json),"
                    "follow_info_json=VALUES(follow_info_json),fetched_at=VALUES(fetched_at);\n"
                )

        for i in range(0, len(links), 80):
            vals = []
            for r in links[i : i + 80]:
                vals.append(
                    "("
                    + ",".join(
                        [
                            week._esc(r.get("follow_userid")),
                            week._esc(r.get("external_userid")),
                            week._esc(r.get("name")),
                            week._esc(r.get("remark")),
                            week._esc(r.get("createtime")),
                            week._esc(r.get("add_way")),
                            week._esc(r.get("state")),
                            week._esc(r.get("tag_id")),
                            week._esc(r.get("tag_name")),
                            week._esc(r.get("group_id")),
                            week._esc(r.get("group_name")),
                            week._esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                f.write(
                    "INSERT INTO qywx_contact_tag_link "
                    "(follow_userid,external_userid,name,remark,createtime,add_way,state,"
                    "tag_id,tag_name,group_id,group_name,fetched_at) VALUES\n"
                )
                f.write(",\n".join(vals) + ";\n")

        if follows:
            fvals = [
                f"({week._esc(uid)},{week._esc(name)},{week._esc(now)})"
                for uid, name in sorted(follows.items())
            ]
            for i in range(0, len(fvals), 100):
                f.write(
                    "INSERT INTO qywx_follow_user (follow_userid,follow_name,fetched_at) VALUES\n"
                )
                f.write(",\n".join(fvals[i : i + 100]) + "\n")
                f.write(
                    "ON DUPLICATE KEY UPDATE follow_name=VALUES(follow_name),"
                    "fetched_at=VALUES(fetched_at);\n"
                )
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def write_pay_upsert_sql(path: Path, flats: list[dict[str, Any]], begin_time: int, end_time: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("w", encoding="utf-8") as f:
        f.write(f"-- pay upsert range {begin_time}~{end_time}\n")
        f.write("SET NAMES utf8mb4;\n")
        f.write(
            f"""
CREATE TABLE IF NOT EXISTS {PAY_TABLE} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  transaction_id VARCHAR(64) NULL,
  out_trade_no VARCHAR(64) NULL,
  out_refund_no VARCHAR(64) NULL,
  pay_time INT UNSIGNED NULL,
  payment_type INT NULL,
  trade_state INT NULL,
  bill_type INT NULL,
  total_fee BIGINT NULL,
  total_refund_fee BIGINT NULL,
  commodity VARCHAR(512) NULL,
  remark VARCHAR(512) NULL,
  payee_userid VARCHAR(64) NULL,
  external_userid VARCHAR(64) NULL,
  mch_id VARCHAR(64) NULL,
  contact_name VARCHAR(128) NULL,
  contact_phone VARCHAR(64) NULL,
  unionid VARCHAR(64) NULL,
  third_uid VARCHAR(64) NULL,
  xet_user_id VARCHAR(64) NULL,
  bind_phone VARCHAR(32) NULL,
  raw_json MEDIUMTEXT NULL,
  range_begin INT UNSIGNED NULL,
  range_end INT UNSIGNED NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_tx_bill (transaction_id, bill_type, out_refund_no),
  KEY idx_pay_time (pay_time),
  KEY idx_payee (payee_userid),
  KEY idx_external (external_userid),
  KEY idx_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
        )
        # 兼容旧表缺列
        for col, ddl in [
            ("unionid", "ADD COLUMN unionid VARCHAR(64) NULL"),
            ("third_uid", "ADD COLUMN third_uid VARCHAR(64) NULL"),
            ("xet_user_id", "ADD COLUMN xet_user_id VARCHAR(64) NULL"),
            ("bind_phone", "ADD COLUMN bind_phone VARCHAR(32) NULL"),
        ]:
            f.write(
                f"SET @c := (SELECT COUNT(*) FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{PAY_TABLE}' AND COLUMN_NAME='{col}');\n"
                f"SET @s := IF(@c=0, 'ALTER TABLE {PAY_TABLE} {ddl}', 'SELECT 1');\n"
                f"PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;\n"
            )

        f.write(
            f"DELETE FROM {PAY_TABLE} WHERE pay_time >= {begin_time} AND pay_time <= {end_time};\n"
        )
        cols = (
            "transaction_id,out_trade_no,out_refund_no,pay_time,payment_type,trade_state,bill_type,"
            "total_fee,total_refund_fee,commodity,remark,payee_userid,external_userid,mch_id,"
            "contact_name,contact_phone,raw_json,range_begin,range_end,fetched_at"
        )
        for i in range(0, len(flats), 40):
            vals = []
            for r in flats[i : i + 40]:
                vals.append(
                    "("
                    + ",".join(
                        [
                            week._esc(r.get("transaction_id")),
                            week._esc(r.get("out_trade_no")),
                            week._esc(r.get("out_refund_no")),
                            week._esc(r.get("pay_time")),
                            week._esc(r.get("payment_type")),
                            week._esc(r.get("trade_state")),
                            week._esc(r.get("bill_type")),
                            week._esc(r.get("total_fee")),
                            week._esc(r.get("total_refund_fee")),
                            week._esc(r.get("commodity")),
                            week._esc(r.get("remark")),
                            week._esc(r.get("payee_userid")),
                            week._esc(r.get("external_userid")),
                            week._esc(r.get("mch_id")),
                            week._esc(r.get("contact_name")),
                            week._esc(r.get("contact_phone")),
                            week._esc(r.get("raw_json")),
                            week._esc(begin_time),
                            week._esc(end_time),
                            week._esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                f.write(f"INSERT INTO {PAY_TABLE} ({cols}) VALUES\n")
                f.write(",\n".join(vals) + ";\n")


def maybe_override_db_host(db_host: str) -> None:
    if not db_host:
        return
    url = (os.getenv("LEGACY_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return
    url2 = re.sub(r"@[^:/]+", f"@{db_host}", url, count=1)
    os.environ["LEGACY_DATABASE_URL"] = url2
    os.environ["DATABASE_URL"] = url2
    _log(f"DB host override -> {db_host}")


def run_enrich_sql(db_host: str) -> Path | None:
    maybe_override_db_host(db_host)
    import export_qywx_pay_bill_enrich_sql as enrich

    # 复用其 main：通过修改 argv
    old = sys.argv
    try:
        sys.argv = ["export_qywx_pay_bill_enrich_sql.py"]
        code = enrich.main()
        if code != 0:
            raise RuntimeError("enrich 失败")
    finally:
        sys.argv = old
    files = sorted(EXPORT.glob("qywx_pay_bill_enrich_update_*.sql"))
    return files[-1] if files else None


def apply_sql_files(files: list[Path], db_host: str) -> None:
    maybe_override_db_host(db_host)
    import pymysql

    url = (os.getenv("LEGACY_DATABASE_URL") or "").strip()
    m = re.match(
        r"(?:mysql(?:\+pymysql)?://)?([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)",
        url,
    )
    if not m:
        raise RuntimeError("无法解析 LEGACY_DATABASE_URL")
    conn = pymysql.connect(
        host=m.group(3),
        port=int(m.group(4) or 3306),
        user=unquote(m.group(1)),
        password=unquote(m.group(2)),
        database=m.group(5),
        charset="utf8mb4",
        autocommit=True,
    )
    cur = conn.cursor()
    for p in files:
        _log(f"APPLY {p.name} ...")
        sql = p.read_text(encoding="utf-8")
        # 简单按分号执行（够用）
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s or s.startswith("--"):
                continue
            try:
                cur.execute(s)
            except Exception as e:
                # 忽略重复加列类错误
                msg = str(e)
                if "Duplicate column" in msg or "already exists" in msg.lower():
                    continue
                raise
        _log(f"  ok {p.name}")
    conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="企微近N天同步 + 历史增量补全")
    ap.add_argument("--recent-days", type=int, default=7)
    ap.add_argument("--history-batch", type=int, default=200, help="每轮历史补全客户数")
    ap.add_argument(
        "--history-max-days",
        type=int,
        default=0,
        help="历史只补 add_time 在近 X 天内的；0=全部未同步客户",
    )
    ap.add_argument("--pay-history-days", type=int, default=30, help="收款再往前补多少天（不含近N天）")
    ap.add_argument("--from-json", default="", help="跳过 contact_list，用本地缓存")
    ap.add_argument("--skip-served", action="store_true")
    ap.add_argument("--skip-pay", action="store_true")
    ap.add_argument("--skip-detail", action="store_true")
    ap.add_argument("--skip-enrich", action="store_true")
    ap.add_argument("--recent-only", action="store_true")
    ap.add_argument("--history-only", action="store_true")
    ap.add_argument("--enrich-only", action="store_true")
    ap.add_argument("--db-host", default="", help="本机连库用外网域名")
    ap.add_argument("--apply", action="store_true", help="直接执行生成的 SQL 写库")
    ap.add_argument("--limit", type=int, default=0, help="调试：限制详情拉取人数")
    args = ap.parse_args()

    EXPORT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    synced: set[str] = set(state.get("synced_external_userids") or [])
    failed: dict[str, str] = dict(state.get("failed_external_userids") or {})
    out_files: list[Path] = []
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")

    if args.enrich_only:
        p = run_enrich_sql(args.db_host)
        if p:
            _log(f"enrich SQL: {p}")
            if args.apply:
                apply_sql_files([p], args.db_host)
        return 0

    token = get_token()

    # ---- 1) served list ----
    if args.from_json:
        cache = Path(args.from_json)
        if not cache.is_absolute():
            cache = ROOT / cache
        rows = json.loads(cache.read_text(encoding="utf-8")).get("rows") or []
        _log(f"使用缓存 {cache.name} rows={len(rows)}")
    elif args.skip_served and not args.history_only:
        cands = sorted(EXPORT.glob("qywx_served_contacts_*.json"))
        if not cands:
            raise RuntimeError("无 served 缓存，请去掉 --skip-served")
        cache = cands[-1]
        rows = json.loads(cache.read_text(encoding="utf-8")).get("rows") or []
        _log(f"复用缓存 {cache.name} rows={len(rows)}")
    else:
        _log("=== 1/4 拉取已服务外部联系人 contact_list ===")
        rows = fetch_contact_list(token)
        cache = save_served_cache(rows)

    tag_map: dict[str, dict[str, Any]] = {}
    if not args.skip_detail:
        _log("拉取企业标签库 ...")
        tag_map = week.fetch_tag_map(token)
        _log(f"  tag={len(tag_map)}")

    # ---- 2) recent ----
    if not args.history_only:
        _log(f"=== 2/4 近 {args.recent_days} 天关联数据 ===")
        eids, pairs, since_ts = recent_scope(rows, args.recent_days)
        if args.limit > 0:
            eids = eids[: args.limit]
        _log(f"近{args.recent_days}天客户 {len(eids)}，关系对 {len(pairs)}")

        if not args.skip_detail and eids:
            details, fulls, links, follow_ids = process_details(
                token, eids, pairs, since_ts, tag_map, include_all_follows=False
            )
            follows = week.fetch_follow_names(token, sorted(follow_ids)) if follow_ids else {}
            sql_path = EXPORT / f"qywx_pipeline_recent_{args.recent_days}d_{stamp}.sql"
            write_upsert_sql(
                sql_path,
                details=details,
                fulls=fulls,
                tag_map=tag_map,
                links=links,
                follows=follows,
                recreate_tags=True,
            )
            out_files.append(sql_path)
            for d in details:
                eid = d.get("external_userid")
                if not eid:
                    continue
                if d.get("errcode"):
                    failed[eid] = str(d.get("errmsg") or d.get("errcode"))
                else:
                    synced.add(eid)
                    failed.pop(eid, None)
            _log(f"已写 {sql_path.name}")

        if not args.skip_pay:
            end = datetime.now()
            begin = end - timedelta(days=args.recent_days)
            bts, ets = int(begin.timestamp()), int(end.timestamp())
            _log(f"拉取收款 {begin} ~ {end}")
            bills = pay.fetch_bills(token, bts, ets)
            flats = [pay.flatten(b) for b in bills]
            pay_sql = EXPORT / f"qywx_pipeline_pay_{args.recent_days}d_{stamp}.sql"
            write_pay_upsert_sql(pay_sql, flats, bts, ets)
            out_files.append(pay_sql)
            _log(f"收款 {len(flats)} 条 -> {pay_sql.name}")

            # 收款历史窗口（近 N 天之前再补一段）
            if args.pay_history_days > 0 and not args.recent_only:
                end2 = begin
                begin2 = end2 - timedelta(days=args.pay_history_days)
                b2, e2 = int(begin2.timestamp()), int(end2.timestamp())
                _log(f"补收款历史 {begin2} ~ {end2}")
                bills2 = pay.fetch_bills(token, b2, e2)
                flats2 = [pay.flatten(b) for b in bills2]
                pay_sql2 = EXPORT / f"qywx_pipeline_pay_hist_{args.pay_history_days}d_{stamp}.sql"
                write_pay_upsert_sql(pay_sql2, flats2, b2, e2)
                out_files.append(pay_sql2)
                _log(f"历史收款 {len(flats2)} 条 -> {pay_sql2.name}")

    # ---- 3) history detail batch ----
    if not args.recent_only:
        _log(f"=== 3/4 历史详情增量（每批 {args.history_batch}）===")
        all_ids = all_external_ids(rows)
        if args.history_max_days > 0:
            since_h = int((datetime.now() - timedelta(days=args.history_max_days)).timestamp())
            allow = {
                (r.get("external_userid") or "").strip()
                for r in rows
                if int(r.get("add_time") or 0) >= since_h and r.get("external_userid")
            }
            all_ids = [x for x in all_ids if x in allow]
        pending = [x for x in all_ids if x not in synced]
        _log(f"总客户 {len(all_ids)}，已同步 {len(synced)}，待补 {len(pending)}")
        batch = pending[: args.history_batch]
        if args.limit > 0:
            batch = batch[: args.limit]
        if batch and not args.skip_detail:
            if not tag_map:
                tag_map = week.fetch_tag_map(token)
            details, fulls, links, follow_ids = process_details(
                token, batch, pairs=None, since_ts=None, tag_map=tag_map, include_all_follows=True
            )
            follows = week.fetch_follow_names(token, sorted(follow_ids)) if follow_ids else {}
            hist_sql = EXPORT / f"qywx_pipeline_history_{len(batch)}_{stamp}.sql"
            write_upsert_sql(
                hist_sql,
                details=details,
                fulls=fulls,
                tag_map=tag_map,
                links=links,
                follows=follows,
                recreate_tags=False,
            )
            out_files.append(hist_sql)
            for d in details:
                eid = d.get("external_userid")
                if not eid:
                    continue
                if d.get("errcode"):
                    failed[eid] = str(d.get("errmsg") or d.get("errcode"))
                    # 失败也标记，避免死循环；可手动清 state 重试
                    synced.add(eid)
                else:
                    synced.add(eid)
                    failed.pop(eid, None)
            _log(f"本批完成 {len(batch)}，剩余约 {max(0, len(pending) - len(batch))}；SQL={hist_sql.name}")
        elif not batch:
            _log("历史已补完（无待同步客户）")

    # ---- 4) enrich ----
    if not args.skip_enrich and not args.history_only:
        _log("=== 4/4 生成收款 UnionID 关联 SQL ===")
        try:
            enrich_path = run_enrich_sql(args.db_host)
            if enrich_path:
                out_files.append(enrich_path)
                _log(f"enrich -> {enrich_path.name}")
        except Exception as e:
            _log(f"[warn] enrich 跳过（库不可达或表不齐）: {e}")

    state["synced_external_userids"] = sorted(synced)
    state["failed_external_userids"] = failed
    save_state(state)

    if args.apply and out_files:
        _log("=== APPLY 写库 ===")
        apply_sql_files(out_files, args.db_host)

    _log("")
    _log("完成。生成文件:")
    for p in out_files:
        _log(f"  {p} ({p.stat().st_size // 1024} KB)")
    _log(f"进度: {STATE_PATH}")
    _log(
        "服务器导入示例:\n"
        "  mysql -h内网地址 -ujingnao -p db_fz_jingnao < docs/export/qywx_pipeline_recent_7d_XXX.sql\n"
        "历史未完则重复:\n"
        "  python -u backend/tools/sync_wework_pipeline.py --history-only --history-batch 200"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
