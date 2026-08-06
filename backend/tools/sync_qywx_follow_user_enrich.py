#!/usr/bin/env python3
"""同步员工到 qywx_follow_user：企微手机号 + 按手机号关联小程序/小鹅通。

写入字段:
  follow_userid, follow_name, mobile,
  unionid, third_uid, xet_user_id, bind_phone, fetched_at

手机号来源（优先级）:
  1) --mobile-csv 手工映射（follow_userid,mobile）
  2) user/get 返回的 mobile / telephone（需应用有敏感字段权限；当前客户联系应用通常为空）
  3) follow_userid 本身是 11 位手机号时直接使用
  4) 可选环境变量 WEWORK_CONTACT_SECRET（通讯录类 Secret）再试一次 user/get

关联:
  mobile -> ys_third_party_user.mobile -> third_uid + unionid
  mobile -> ys_xet_user_lists.bind_phone -> xet_user_id + unionid
  unionid 优先取「两端一致」；否则 third；再否则 xet

用法（宝塔 / Docker）:
  docker exec -it jnao-daka-backend python -u tools/sync_qywx_follow_user_enrich.py --apply
  docker exec -it jnao-daka-backend python -u tools/sync_qywx_follow_user_enrich.py --apply --mobile-csv /app/data/qywx_export/follow_mobile.csv

本地（外网 RDS）:
  python -u backend/tools/sync_qywx_follow_user_enrich.py --db-host rm-xxxno.mysql.rds.aliyuncs.com --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pymysql
import requests

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from _wework_paths import export_dir, load_env, project_roots  # noqa: E402

BACKEND, ROOT = project_roots(__file__)
load_env(BACKEND, ROOT)
EXPORT = export_dir(BACKEND, ROOT)
EXPORT.mkdir(parents=True, exist_ok=True)

QYAPI = "https://qyapi.weixin.qq.com/cgi-bin"
TABLE = "qywx_follow_user"
MOBILE_RE = re.compile(r"^1\d{10}$")


def _log(msg: str) -> None:
    print(msg, flush=True)


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


def connect_db() -> pymysql.connections.Connection:
    url = (os.getenv("LEGACY_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    m = re.match(
        r"(?:mysql(?:\+pymysql)?://)?([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)",
        url,
    )
    if not m:
        raise RuntimeError("无法解析 LEGACY_DATABASE_URL")
    return pymysql.connect(
        host=m.group(3),
        port=int(m.group(4) or 3306),
        user=unquote(m.group(1)),
        password=unquote(m.group(2)),
        database=m.group(5),
        charset="utf8mb4",
        connect_timeout=20,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_token(secret: str | None = None) -> str:
    corpid = (os.getenv("WEWORK_CORPID") or "").strip()
    sec = (secret or os.getenv("WEWORK_CORPSECRET") or "").strip()
    if not corpid or not sec:
        raise RuntimeError("缺少 WEWORK_CORPID / WEWORK_CORPSECRET")
    d = requests.get(
        f"{QYAPI}/gettoken",
        params={"corpid": corpid, "corpsecret": sec},
        timeout=30,
    ).json()
    if d.get("errcode", 0) != 0 or not d.get("access_token"):
        raise RuntimeError(f"gettoken 失败: {d}")
    return d["access_token"]


def norm_mobile(v: Any) -> str | None:
    if v is None:
        return None
    s = re.sub(r"\D", "", str(v).strip())
    if len(s) > 11 and s.startswith("86"):
        s = s[-11:]
    if MOBILE_RE.fullmatch(s):
        return s
    return None


def ensure_schema(cur: Any) -> None:
    cur.execute(
        f"""
CREATE TABLE IF NOT EXISTS `{TABLE}` (
  follow_userid VARCHAR(64) NOT NULL,
  follow_name VARCHAR(128) NULL,
  mobile VARCHAR(32) NULL COMMENT '员工手机号',
  unionid VARCHAR(64) NULL COMMENT '微信unionid(手机号关联)',
  third_uid VARCHAR(64) NULL COMMENT 'ys_third_party_user.uid',
  xet_user_id VARCHAR(64) NULL COMMENT 'ys_xet_user_lists.user_id',
  bind_phone VARCHAR(32) NULL COMMENT '小鹅通 bind_phone',
  position VARCHAR(128) NULL,
  department_json TEXT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (follow_userid),
  KEY idx_mobile (mobile),
  KEY idx_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='企微跟进员工+三端关联'
"""
    )
    for col, ddl in [
        ("mobile", "ADD COLUMN mobile VARCHAR(32) NULL COMMENT '员工手机号' AFTER follow_name"),
        ("unionid", "ADD COLUMN unionid VARCHAR(64) NULL COMMENT '微信unionid' AFTER mobile"),
        ("third_uid", "ADD COLUMN third_uid VARCHAR(64) NULL COMMENT 'ys_third_party_user.uid' AFTER unionid"),
        ("xet_user_id", "ADD COLUMN xet_user_id VARCHAR(64) NULL COMMENT 'ys_xet_user_lists.user_id' AFTER third_uid"),
        ("bind_phone", "ADD COLUMN bind_phone VARCHAR(32) NULL COMMENT '小鹅通bind_phone' AFTER xet_user_id"),
        ("position", "ADD COLUMN position VARCHAR(128) NULL AFTER bind_phone"),
        ("department_json", "ADD COLUMN department_json TEXT NULL AFTER position"),
    ]:
        cur.execute(
            "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            (TABLE, col),
        )
        if cur.fetchone()["c"] == 0:
            cur.execute(f"ALTER TABLE `{TABLE}` {ddl}")
            _log(f"  ALTER add {col}")


def load_mobile_csv(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"mobile csv 不存在: {p}")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # 兼容无表头两列
        if reader.fieldnames and (
            "follow_userid" not in {h.strip().lower() for h in reader.fieldnames}
            and "userid" not in {h.strip().lower() for h in reader.fieldnames}
        ):
            f.seek(0)
            for row in csv.reader(f):
                if len(row) < 2:
                    continue
                uid, mob = row[0].strip(), norm_mobile(row[1])
                if uid and mob:
                    out[uid] = mob
            return out
        for row in reader:
            keys = {k.lower().strip(): k for k in row.keys() if k}
            uid_k = keys.get("follow_userid") or keys.get("userid") or keys.get("员工userid")
            mob_k = keys.get("mobile") or keys.get("phone") or keys.get("手机号") or keys.get("手机")
            if not uid_k or not mob_k:
                continue
            uid = (row.get(uid_k) or "").strip()
            mob = norm_mobile(row.get(mob_k))
            if uid and mob:
                out[uid] = mob
    return out


def collect_userids(cur: Any, only_table: bool = True) -> list[str]:
    """默认只处理 qywx_follow_user 已有员工。"""
    ids: set[str] = set()
    sqls = [f"SELECT follow_userid AS u FROM `{TABLE}`"]
    if not only_table:
        sqls.extend(
            [
                "SELECT DISTINCT payee_userid AS u FROM qywx_pay_bill "
                "WHERE payee_userid IS NOT NULL AND payee_userid<>''",
                "SELECT DISTINCT follow_userid AS u FROM qywx_external_contact_full "
                "WHERE follow_userid IS NOT NULL AND follow_userid<>''",
            ]
        )
    for sql in sqls:
        try:
            cur.execute(sql)
            for r in cur.fetchall():
                u = (r.get("u") or "").strip()
                if u:
                    ids.add(u)
        except Exception:  # noqa: BLE001
            pass
    return sorted(ids)


def fetch_user(token: str, userid: str, retries: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return requests.get(
                f"{QYAPI}/user/get",
                params={"access_token": token, "userid": userid},
                timeout=30,
            ).json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
            _log(f"  [retry {attempt}/{retries}] user/get {userid}: {type(e).__name__}")
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"user/get {userid} 失败: {last}") from last


def pick_mobile_from_api(d: dict[str, Any]) -> str | None:
    """仅从 user/get 响应取手机号（不含 userid 回退）。"""
    for key in ("mobile", "telephone"):
        m = norm_mobile(d.get(key))
        if m:
            return m
    attrs = ((d.get("extattr") or {}).get("attrs")) or []
    for a in attrs:
        val = a.get("value")
        if val is None and isinstance(a.get("text"), dict):
            val = a["text"].get("value")
        m = norm_mobile(val)
        if m:
            return m
    return None


def build_mobile_maps(
    cur: Any,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """mobile -> third/xet 候选列表（同号可能多条）。"""
    third: dict[str, list[dict[str, Any]]] = {}
    cur.execute(
        "SELECT uid, mobile, unionid, openid, nickname FROM ys_third_party_user "
        "WHERE mobile IS NOT NULL AND mobile<>''"
    )
    for r in cur.fetchall():
        m = norm_mobile(r["mobile"])
        if m:
            third.setdefault(m, []).append(r)

    xet: dict[str, list[dict[str, Any]]] = {}
    cur.execute(
        "SELECT user_id, bind_phone, wx_union_id, user_nickname FROM ys_xet_user_lists "
        "WHERE bind_phone IS NOT NULL AND bind_phone<>''"
    )
    for r in cur.fetchall():
        m = norm_mobile(r["bind_phone"])
        if m:
            xet.setdefault(m, []).append(r)
    return third, xet


def _pick_xet(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    with_u = [r for r in rows if (r.get("wx_union_id") or "").strip()]
    return (with_u or rows)[0]


def _pick_third(rows: list[dict[str, Any]], prefer_union: str | None) -> dict[str, Any] | None:
    if not rows:
        return None
    if prefer_union:
        for r in rows:
            if (r.get("unionid") or "").strip() == prefer_union:
                return r
    with_u = [r for r in rows if (r.get("unionid") or "").strip()]
    return (with_u or rows)[0]


def resolve_links(
    mobile: str | None,
    third_map: dict[str, list[dict[str, Any]]],
    xet_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if not mobile:
        return {
            "unionid": None,
            "third_uid": None,
            "xet_user_id": None,
            "bind_phone": None,
        }
    x = _pick_xet(xet_map.get(mobile) or [])
    x_id = (x.get("user_id") or "").strip() or None if x else None
    x_union = (x.get("wx_union_id") or "").strip() or None if x else None
    t = _pick_third(third_map.get(mobile) or [], x_union)
    t_uid = str(t["uid"]) if t and t.get("uid") is not None else None
    t_union = (t.get("unionid") or "").strip() or None if t else None
    union = None
    if t_union and x_union and t_union == x_union:
        union = t_union
    elif x_union:
        union = x_union
    elif t_union:
        union = t_union
    return {
        "unionid": union,
        "third_uid": t_uid,
        "xet_user_id": x_id,
        "bind_phone": mobile,
    }


def upsert_row(cur: Any, row: dict[str, Any]) -> None:
    cur.execute(
        f"""
INSERT INTO `{TABLE}` (
  follow_userid, follow_name, mobile, unionid, third_uid, xet_user_id,
  bind_phone, position, department_json, fetched_at
) VALUES (
  %(follow_userid)s, %(follow_name)s, %(mobile)s, %(unionid)s, %(third_uid)s, %(xet_user_id)s,
  %(bind_phone)s, %(position)s, %(department_json)s, %(fetched_at)s
)
ON DUPLICATE KEY UPDATE
  follow_name=VALUES(follow_name),
  mobile=COALESCE(VALUES(mobile), mobile),
  unionid=VALUES(unionid),
  third_uid=VALUES(third_uid),
  xet_user_id=VALUES(xet_user_id),
  bind_phone=VALUES(bind_phone),
  position=COALESCE(VALUES(position), position),
  department_json=COALESCE(VALUES(department_json), department_json),
  fetched_at=VALUES(fetched_at)
""",
        row,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="员工手机号 + 三端关联写入 qywx_follow_user")
    ap.add_argument("--apply", action="store_true", help="写库（默认只预览统计）")
    ap.add_argument("--db-host", default="", help="覆盖 RDS 主机（本机外网）")
    ap.add_argument("--mobile-csv", default="", help="可选 CSV: follow_userid,mobile")
    ap.add_argument(
        "--expand",
        action="store_true",
        help="额外纳入 pay_bill/full 的员工（默认只处理本表已有）",
    )
    ap.add_argument(
        "--skip-api",
        action="store_true",
        help="不调企微接口，仅用表内/CSV/userid 手机号做三端拼接",
    )
    ap.add_argument("--sleep", type=float, default=0.03)
    args = ap.parse_args()

    maybe_override_db_host(args.db_host)
    csv_map = load_mobile_csv(args.mobile_csv) if args.mobile_csv else {}
    if csv_map:
        _log(f"mobile csv 载入 {len(csv_map)} 条")

    token = None
    contact_token = None
    if not args.skip_api:
        token = get_token()
        contact_secret = (os.getenv("WEWORK_CONTACT_SECRET") or "").strip()
        if contact_secret:
            try:
                contact_token = get_token(contact_secret)
                _log("已加载 WEWORK_CONTACT_SECRET 备用 token")
            except Exception as e:  # noqa: BLE001
                _log(f"[warn] CONTACT_SECRET 不可用: {e}")

    conn = connect_db()
    cur = conn.cursor()
    ensure_schema(cur)
    conn.commit()

    userids = collect_userids(cur, only_table=not args.expand)
    _log(f"待同步员工 {len(userids)} 人（only_table={not args.expand}）")
    third_map, xet_map = build_mobile_maps(cur)
    _log(f"手机号索引 third={len(third_map)} xet={len(xet_map)}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = {
        "total": 0,
        "api_ok": 0,
        "api_fail": 0,
        "has_mobile": 0,
        "mobile_from_csv": 0,
        "mobile_from_api": 0,
        "mobile_from_userid": 0,
        "mobile_from_db": 0,
        "hit_third": 0,
        "hit_xet": 0,
        "has_union": 0,
        "both_union_same": 0,
    }
    preview: list[dict[str, Any]] = []

    for i, uid in enumerate(userids, 1):
        stats["total"] += 1
        cur.execute(f"SELECT * FROM `{TABLE}` WHERE follow_userid=%s", (uid,))
        old = cur.fetchone() or {}

        d: dict[str, Any] = {}
        api_ok = False
        if token:
            d = fetch_user(token, uid)
            if (d.get("errcode") or 0) != 0 and contact_token:
                d2 = fetch_user(contact_token, uid)
                if (d2.get("errcode") or 0) == 0:
                    d = d2
            api_ok = (d.get("errcode") or 0) == 0
            if api_ok:
                stats["api_ok"] += 1
            else:
                stats["api_fail"] += 1
                if i == 1:
                    _log(f"[warn] user/get 失败: {d.get('errcode')} {d.get('errmsg')}")

        name = (d.get("name") if api_ok else None) or old.get("follow_name")

        mobile = None
        src = None
        if uid in csv_map:
            mobile = csv_map[uid]
            src = "csv"
            stats["mobile_from_csv"] += 1
        if not mobile and api_ok:
            m_api = pick_mobile_from_api(d)
            if m_api:
                mobile = m_api
                src = "api"
                stats["mobile_from_api"] += 1
        if not mobile:
            m_uid = norm_mobile(uid)
            if m_uid:
                mobile = m_uid
                src = "userid"
                stats["mobile_from_userid"] += 1
        if not mobile:
            m_db = norm_mobile(old.get("mobile"))
            if m_db:
                mobile = m_db
                src = "db"
                stats["mobile_from_db"] += 1

        links = resolve_links(mobile, third_map, xet_map)
        if mobile:
            stats["has_mobile"] += 1
        if links["third_uid"]:
            stats["hit_third"] += 1
        if links["xet_user_id"]:
            stats["hit_xet"] += 1
        if links["unionid"]:
            stats["has_union"] += 1
        t_list = third_map.get(mobile or "") or []
        x_list = xet_map.get(mobile or "") or []
        t = _pick_third(t_list, links["unionid"])
        x = _pick_xet(x_list)
        if (
            t
            and x
            and (t.get("unionid") or "").strip()
            and (t.get("unionid") or "").strip() == (x.get("wx_union_id") or "").strip()
        ):
            stats["both_union_same"] += 1

        position = (d.get("position") if api_ok else None) or old.get("position")
        if api_ok:
            dept_json = json.dumps(d.get("department") or [], ensure_ascii=False)
        else:
            dept_json = old.get("department_json")

        row = {
            "follow_userid": uid,
            "follow_name": name,
            "mobile": mobile,
            "unionid": links["unionid"],
            "third_uid": links["third_uid"],
            "xet_user_id": links["xet_user_id"],
            "bind_phone": mobile,
            "position": position,
            "department_json": dept_json,
            "fetched_at": now,
        }
        preview.append({**row, "_mobile_src": src})
        if args.apply:
            upsert_row(cur, row)
        if i % 20 == 0 or i == len(userids):
            _log(
                f"  {i}/{len(userids)} mobile={stats['has_mobile']} "
                f"third={stats['hit_third']} xet={stats['hit_xet']} union={stats['has_union']}"
            )
            if args.apply:
                conn.commit()
        if token:
            time.sleep(args.sleep)

    if args.apply:
        conn.commit()
        _log("已写库 APPLY ok")
    else:
        _log("预览模式未写库（加 --apply 写库）")

    _log(f"统计: {stats}")
    _log("样例（最多 12 条）:")
    for r in preview[:12]:
        _log(
            f"  {r['follow_userid']}: name={r['follow_name']!r} mobile={r['mobile']} "
            f"src={r.get('_mobile_src')} unionid={r['unionid']} "
            f"third={r['third_uid']} xet={r['xet_user_id']}"
        )

    if stats["mobile_from_api"] == 0 and stats["has_mobile"] < stats["total"]:
        _log("")
        _log(
            "注意: 当前 WEWORK_CORPSECRET 对应应用的 user/get 未返回 mobile（企微敏感字段限制）。"
            "仅 userid 本身是手机号的员工、或 --mobile-csv 可关联三端。"
            "可从企微后台导出成员手机号 CSV 后："
            "  --mobile-csv /app/data/qywx_export/follow_mobile.csv"
        )

    # 导出一份结果便于核对
    out = EXPORT / f"qywx_follow_user_enrich_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "follow_userid",
                "follow_name",
                "mobile",
                "mobile_src",
                "unionid",
                "third_uid",
                "xet_user_id",
                "bind_phone",
                "position",
            ],
        )
        w.writeheader()
        for r in preview:
            w.writerow(
                {
                    "follow_userid": r["follow_userid"],
                    "follow_name": r["follow_name"],
                    "mobile": r["mobile"],
                    "mobile_src": r.get("_mobile_src"),
                    "unionid": r["unionid"],
                    "third_uid": r["third_uid"],
                    "xet_user_id": r["xet_user_id"],
                    "bind_phone": r["bind_phone"],
                    "position": r["position"],
                }
            )
    _log(f"结果 CSV: {out}")
    conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        _log(f"[ERROR] {e}")
        raise
