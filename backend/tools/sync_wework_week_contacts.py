#!/usr/bin/env python3
"""同步近 N 天客户详情（含 unionid）+ 企业标签库 + 客户标签关联。

数据源：已服务外部联系人缓存中近 N 天的 external_userid。
接口：
  GET  /cgi-bin/externalcontact/get                 → 客户详情（unionid / follow_user）
  POST /cgi-bin/externalcontact/get_corp_tag_list   → 企业标签库
  GET  /cgi-bin/user/get                            → 跟进人姓名（可选）

产出表（一份 SQL，导入时会 DROP/重建下列表，不影响 served_*）：
  qywx_external_contact_detail  客户主表（一人一行，含 unionid）
  qywx_external_contact_full    跟进人×客户（一周关系明细）
  qywx_corp_tag                 企业标签库
  qywx_contact_tag_link         客户×标签交叉
  qywx_follow_user              跟进人维度

用法:
  python -u backend/tools/sync_wework_week_contacts.py --days 7
  python -u backend/tools/sync_wework_week_contacts.py --days 7 --from-json docs/export/xxx.json
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
EXPORT = ROOT / "docs" / "export"


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


def resolve_source(path: str) -> Path:
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise RuntimeError(f"找不到源文件: {p}")
        return p
    cands = sorted(EXPORT.glob("*plan_a_7d_enriched.json")) + sorted(
        EXPORT.glob("qywx_served_contacts_*_enriched.json")
    )
    if not cands:
        cands = sorted(EXPORT.glob("qywx_served_contacts_*.json"))
    if not cands:
        raise RuntimeError("未找到 served contacts 缓存 JSON")
    return cands[0] if "plan_a_7d" in cands[0].name else cands[-1]


def load_week_scope(src: Path, days: int) -> tuple[list[str], set[tuple[str, str]], int]:
    """返回 external_userid 列表、一周内 (follow, external) 对、since_ts。"""
    data = json.loads(src.read_text(encoding="utf-8"))
    rows = data.get("rows") or []
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


def fetch_one(token: str, external_userid: str) -> dict[str, Any]:
    cursor = ""
    merged: dict[str, Any] = {"external_userid": external_userid, "errcode": 0}
    follow_users: list[dict[str, Any]] = []
    while True:
        params: dict[str, Any] = {"access_token": token, "external_userid": external_userid}
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
        time.sleep(0.02)
    merged["follow_user"] = follow_users
    return merged


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


def fetch_follow_names(token: str, userids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, uid in enumerate(userids, 1):
        d = requests.get(
            f"{QYAPI}/user/get",
            params={"access_token": token, "userid": uid},
            timeout=30,
        ).json()
        if d.get("errcode", 0) == 0 and d.get("name"):
            out[uid] = d["name"]
        if i % 20 == 0 or i == len(userids):
            print(f"  跟进人姓名 {i}/{len(userids)} ok={len(out)}", flush=True)
        time.sleep(0.02)
    return out


def flatten_detail(detail: dict[str, Any]) -> dict[str, Any]:
    ec = detail.get("external_contact") or {}
    follows = detail.get("follow_user") or []
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
    }


def extract_tag_ids(fi: dict[str, Any]) -> list[str]:
    """get 接口多为 tags[{tag_id,...}]；batch 接口多为 tag_id[str]。"""
    tids: list[str] = []
    raw_ids = fi.get("tag_id")
    if isinstance(raw_ids, list) and raw_ids:
        tids.extend(str(x) for x in raw_ids if x)
    for t in fi.get("tags") or []:
        if isinstance(t, dict) and t.get("tag_id"):
            tid = str(t["tag_id"])
            if tid not in tids:
                tids.append(tid)
        elif isinstance(t, str) and t not in tids:
            tids.append(t)
    return tids


def flatten_full(ec: dict[str, Any], fi: dict[str, Any]) -> dict[str, Any]:
    mobiles = fi.get("remark_mobiles") or []
    channels = fi.get("wechat_channels")
    tids = extract_tag_ids(fi)
    return {
        "follow_userid": fi.get("userid"),
        "external_userid": ec.get("external_userid"),
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
        "remark": fi.get("remark"),
        "description": fi.get("description"),
        "createtime": fi.get("createtime"),
        "tag_id_json": json.dumps(tids, ensure_ascii=False) if tids else None,
        "remark_corp_name": fi.get("remark_corp_name"),
        "remark_mobiles_json": json.dumps(mobiles, ensure_ascii=False) if mobiles else None,
        "remark_mobiles": ",".join(str(x) for x in mobiles) if mobiles else None,
        "oper_userid": fi.get("oper_userid"),
        "add_way": fi.get("add_way"),
        "state": fi.get("state"),
        "wechat_channels_nickname": (channels or {}).get("nickname")
        if isinstance(channels, dict)
        else None,
        "wechat_channels_source": (channels or {}).get("source")
        if isinstance(channels, dict)
        else None,
        "wechat_channels_json": json.dumps(channels, ensure_ascii=False)
        if channels is not None
        else None,
        "external_contact_json": json.dumps(ec, ensure_ascii=False),
        "follow_info_json": json.dumps(fi, ensure_ascii=False),
    }


def write_sql(
    path: Path,
    *,
    details: list[dict[str, Any]],
    fulls: list[dict[str, Any]],
    tag_map: dict[str, dict[str, Any]],
    links: list[dict[str, Any]],
    follows: dict[str, str],
    days: int,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("w", encoding="utf-8") as f:
        f.write(f"-- week sync days={days}; rebuild detail/full/tag/link/follow; NOT served_*\n")
        f.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
        f.write(
            """
DROP TABLE IF EXISTS qywx_contact_tag_link_sample;
DROP TABLE IF EXISTS qywx_contact_tag_link;
DROP TABLE IF EXISTS qywx_corp_tag;
DROP TABLE IF EXISTS qywx_external_contact_full;
DROP TABLE IF EXISTS qywx_external_contact_detail;
DROP TABLE IF EXISTS qywx_follow_user;

CREATE TABLE qywx_external_contact_detail (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  external_userid VARCHAR(64) NOT NULL,
  errcode INT NOT NULL DEFAULT 0,
  errmsg VARCHAR(255) NULL,
  name VARCHAR(128) NULL,
  avatar VARCHAR(512) NULL,
  type TINYINT NULL COMMENT '1微信 2企微',
  gender TINYINT NULL,
  unionid VARCHAR(64) NULL COMMENT '绑定微信开发者ID后返回',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='externalcontact/get 客户主表(一周)';

CREATE TABLE qywx_external_contact_full (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一周内跟进人x客户明细';

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

CREATE TABLE qywx_contact_tag_link (
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
  KEY idx_follow (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一周客户与标签交叉';

CREATE TABLE qywx_follow_user (
  follow_userid VARCHAR(64) NOT NULL,
  follow_name VARCHAR(128) NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (follow_userid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一周涉及的跟进人';
"""
        )

        # detail
        cols_d = (
            "external_userid,errcode,errmsg,name,avatar,type,gender,unionid,position,"
            "corp_name,corp_full_name,external_profile_json,follow_user_count,"
            "follow_userids,first_follow_time,follow_user_json,fetched_at"
        )
        for i in range(0, len(details), 50):
            vals = []
            for r in details[i : i + 50]:
                if not r.get("external_userid"):
                    continue
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
                            _esc(now),
                        ]
                    )
                    + ")"
                )
            if vals:
                f.write(f"INSERT INTO qywx_external_contact_detail ({cols_d}) VALUES\n")
                f.write(",\n".join(vals) + ";\n")

        # full
        cols_f = (
            "follow_userid,external_userid,name,position,avatar,corp_name,corp_full_name,"
            "type,gender,unionid,external_profile_json,remark,description,createtime,"
            "tag_id_json,remark_corp_name,remark_mobiles,remark_mobiles_json,oper_userid,"
            "add_way,state,wechat_channels_nickname,wechat_channels_source,wechat_channels_json,"
            "external_contact_json,follow_info_json,fetched_at"
        )
        for i in range(0, len(fulls), 40):
            vals = []
            for r in fulls[i : i + 40]:
                if not r.get("external_userid") or not r.get("follow_userid"):
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
                f.write(f"INSERT INTO qywx_external_contact_full ({cols_f}) VALUES\n")
                f.write(",\n".join(vals) + ";\n")

        # tags
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

        # links
        for i in range(0, len(links), 80):
            vals = []
            for r in links[i : i + 80]:
                vals.append(
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
                )
            if vals:
                f.write(
                    "INSERT INTO qywx_contact_tag_link "
                    "(follow_userid,external_userid,name,remark,createtime,add_way,state,"
                    "tag_id,tag_name,group_id,group_name,fetched_at) VALUES\n"
                )
                f.write(",\n".join(vals) + ";\n")

        # follow users
        if follows:
            fvals = [
                f"({_esc(uid)},{_esc(name)},{_esc(now)})" for uid, name in sorted(follows.items())
            ]
            for i in range(0, len(fvals), 100):
                f.write("INSERT INTO qywx_follow_user (follow_userid,follow_name,fetched_at) VALUES\n")
                f.write(",\n".join(fvals[i : i + 100]) + ";\n")

        f.write("SET FOREIGN_KEY_CHECKS=1;\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--from-json", default="")
    ap.add_argument("--limit", type=int, default=0, help="调试用，只拉前 N 个客户")
    args = ap.parse_args()

    src = resolve_source(args.from_json)
    eids, pairs, since_ts = load_week_scope(src, args.days)
    if args.limit > 0:
        eids = eids[: args.limit]
    print(
        f"源 {src.name} | 近{args.days}天 external_userid={len(eids)} "
        f"served对={len(pairs)} since={datetime.fromtimestamp(since_ts)}",
        flush=True,
    )
    if not eids:
        raise RuntimeError("近一周没有可同步的 external_userid")

    token = get_token()
    print("拉取企业标签库...", flush=True)
    tag_map = fetch_tag_map(token)
    print(f"  tag={len(tag_map)}", flush=True)

    details: list[dict[str, Any]] = []
    fulls: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    follow_ids: set[str] = set()
    union_ok = 0
    fail = 0

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = EXPORT
    out_json = out_dir / f"qywx_week_sync_{args.days}d_{stamp}.json"
    out_sql = out_dir / f"qywx_week_sync_{args.days}d_{stamp}.sql"

    for i, eid in enumerate(eids, 1):
        detail = fetch_one(token, eid)
        flat = flatten_detail(detail)
        details.append(flat)
        if flat.get("errcode", 0) != 0:
            fail += 1
        elif flat.get("unionid"):
            union_ok += 1

        ec = detail.get("external_contact") or {}
        for fi in detail.get("follow_user") or []:
            fid = (fi.get("userid") or "").strip()
            if not fid:
                continue
            ct = int(fi.get("createtime") or 0)
            in_week = ct >= since_ts or (fid, eid) in pairs
            if not in_week:
                continue
            follow_ids.add(fid)
            row = flatten_full(ec, fi)
            fulls.append(row)
            tids = extract_tag_ids(fi)
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
                    # get 返回的 tags 里可能已带名称，优先用接口原值补全
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
            print(
                f"  get {i}/{len(eids)} | detail={len(details)} full={len(fulls)} "
                f"unionid非空={union_ok} fail={fail}",
                flush=True,
            )
            out_json.write_text(
                json.dumps(
                    {
                        "days": args.days,
                        "source": src.name,
                        "detail_count": len(details),
                        "full_count": len(fulls),
                        "link_count": len(links),
                        "unionid_ok": union_ok,
                        "fail": fail,
                        "details": details,
                        "fulls": fulls,
                        "links": links,
                        "tag_map": tag_map,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        time.sleep(0.04)

    print(f"拉取跟进人姓名 {len(follow_ids)} ...", flush=True)
    follow_names = fetch_follow_names(token, sorted(follow_ids))

    write_sql(
        out_sql,
        details=details,
        fulls=fulls,
        tag_map=tag_map,
        links=links,
        follows=follow_names,
        days=args.days,
    )
    out_json.write_text(
        json.dumps(
            {
                "days": args.days,
                "source": src.name,
                "detail_count": len(details),
                "full_count": len(fulls),
                "link_count": len(links),
                "tag_count": len(tag_map),
                "follow_count": len(follow_names),
                "unionid_ok": union_ok,
                "fail": fail,
                "details": details,
                "fulls": fulls,
                "links": links,
                "tag_map": tag_map,
                "follow_names": follow_names,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"完成 days={args.days}\n"
        f"  detail={len(details)} (unionid非空={union_ok}, fail={fail})\n"
        f"  full关系={len(fulls)}\n"
        f"  tag库={len(tag_map)} link={len(links)}\n"
        f"  follow={len(follow_names)}\n"
        f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)\n"
        f"已写 {out_json}\n"
        f"导入:\n"
        f"  mysql -h ... -u jingnao -p db_fz_jingnao < {out_sql.name}\n"
        f"验证 unionid:\n"
        f"  SELECT COUNT(*) total, SUM(unionid IS NOT NULL) has_unionid "
        f"FROM qywx_external_contact_detail;",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
