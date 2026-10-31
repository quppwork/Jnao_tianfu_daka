#!/usr/bin/env python3
"""只读数据库，生成 ys_qywx_pay_bill 回填 SQL（不修改任何表数据）。

关联：
  ys_qywx_pay_bill.external_userid
    -> ys_qywx_external_contact_detail/full.unionid
    -> ys_third_party_user.uid
    -> ys_xet_user_lists.user_id / bind_phone

用法（在能连 RDS 的服务器上）:
  cd /path/to/Jnao_tianfu_daka
  $env:PYTHONIOENCODING=\"utf-8\"   # Windows
  export PYTHONIOENCODING=utf-8     # Linux
  python -u backend/tools/export_qywx_pay_bill_enrich_sql.py

产出:
  docs/export/ys_qywx_pay_bill_enrich_update_YYYYMMDDHHMMSS.sql
把该文件拷到服务器用 mysql 执行即可。
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pymysql

from _wework_paths import export_dir, load_env, project_roots

BACKEND, ROOT = project_roots(__file__)
load_env(BACKEND, ROOT)
EXPORT = export_dir(BACKEND, ROOT)


def parse_url(url: str) -> dict[str, Any]:
    m = re.match(
        r"(?:mysql(?:\+pymysql)?://)?([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)",
        url.strip(),
    )
    if not m:
        raise RuntimeError("无法解析 DATABASE_URL / LEGACY_DATABASE_URL")
    return {
        "user": unquote(m.group(1)),
        "password": unquote(m.group(2)),
        "host": m.group(3),
        "port": int(m.group(4) or 3306),
        "database": m.group(5),
    }


def connect() -> pymysql.connections.Connection:
    url = (os.getenv("LEGACY_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("缺少 LEGACY_DATABASE_URL / DATABASE_URL")
    cfg = parse_url(url)
    print(
        f"连接 {cfg['host']}:{cfg['port']}/{cfg['database']} 用户={cfg['user']}",
        flush=True,
    )
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        connect_timeout=20,
        read_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )


def table_exists(cur, name: str) -> bool:
    cur.execute("SHOW TABLES LIKE %s", (name,))
    return cur.fetchone() is not None


def columns(cur, name: str) -> set[str]:
    cur.execute(f"DESCRIBE `{name}`")
    return {r["Field"] for r in cur.fetchall()}


def pick_union_col(cols: set[str], candidates: list[str]) -> str:
    for c in candidates:
        if c in cols:
            return c
    raise RuntimeError(f"未找到 unionid 字段，现有列含: {sorted(c for c in cols if 'union' in c.lower() or 'uid' in c.lower())}")


def esc(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def main() -> int:
    conn = connect()
    cur = conn.cursor()

    pay_table = "ys_qywx_pay_bill" if table_exists(cur, "ys_qywx_pay_bill") else None
    if not pay_table and table_exists(cur, "qywx_externalpay_bill"):
        pay_table = "qywx_externalpay_bill"
    if not pay_table:
        raise RuntimeError("找不到 ys_qywx_pay_bill / qywx_externalpay_bill")

    need = ["ys_third_party_user", "ys_xet_user_lists"]
    for t in need:
        if not table_exists(cur, t):
            raise RuntimeError(f"缺少表 {t}")

    pay_cols = columns(cur, pay_table)
    third_cols = columns(cur, "ys_third_party_user")
    xet_cols = columns(cur, "ys_xet_user_lists")
    print(f"收款表={pay_table}", flush=True)
    print(f"  pay cols sample: {sorted(pay_cols)[:30]}", flush=True)
    print(f"  third union-like: {[c for c in third_cols if 'union' in c.lower() or c in ('uid','openid')]}", flush=True)
    print(f"  xet union-like: {[c for c in xet_cols if 'union' in c.lower() or c in ('user_id','bind_phone','openid')]}", flush=True)

    third_union = pick_union_col(
        third_cols, ["unionid", "union_id", "wx_unionid", "wx_union_id", "wechat_unionid"]
    )
    xet_union = pick_union_col(
        xet_cols, ["unionid", "union_id", "wx_unionid", "wx_union_id", "wechat_unionid"]
    )
    if "uid" not in third_cols:
        raise RuntimeError("ys_third_party_user 无 uid 字段")
    if "user_id" not in xet_cols:
        raise RuntimeError("ys_xet_user_lists 无 user_id 字段")
    if "bind_phone" not in xet_cols:
        raise RuntimeError("ys_xet_user_lists 无 bind_phone 字段")
    if "external_userid" not in pay_cols:
        raise RuntimeError(f"{pay_table} 无 external_userid")
    if "id" not in pay_cols:
        raise RuntimeError(f"{pay_table} 无 id")

    has_detail = table_exists(cur, "ys_qywx_external_contact_detail")
    has_full = table_exists(cur, "ys_qywx_external_contact_full")
    if not has_detail and not has_full:
        raise RuntimeError("需要 ys_qywx_external_contact_detail 或 ys_qywx_external_contact_full 提供 unionid")

    # 客户ID -> unionid
    union_map: dict[str, str] = {}
    if has_detail:
        cur.execute(
            """
            SELECT external_userid, unionid
            FROM ys_qywx_external_contact_detail
            WHERE external_userid IS NOT NULL AND external_userid <> ''
              AND unionid IS NOT NULL AND unionid <> ''
            """
        )
        for r in cur.fetchall():
            union_map[r["external_userid"]] = r["unionid"]
        print(f"detail 映射 {len(union_map)}", flush=True)
    if has_full:
        cur.execute(
            """
            SELECT external_userid, MAX(unionid) AS unionid
            FROM ys_qywx_external_contact_full
            WHERE external_userid IS NOT NULL AND external_userid <> ''
              AND unionid IS NOT NULL AND unionid <> ''
            GROUP BY external_userid
            """
        )
        n = 0
        for r in cur.fetchall():
            if r["external_userid"] not in union_map:
                union_map[r["external_userid"]] = r["unionid"]
                n += 1
        print(f"full 补映射 +{n}，合计 {len(union_map)}", flush=True)

    # unionid -> third uid / xet
    cur.execute(
        f"""
        SELECT `{third_union}` AS unionid, MAX(uid) AS uid
        FROM ys_third_party_user
        WHERE `{third_union}` IS NOT NULL AND `{third_union}` <> ''
        GROUP BY `{third_union}`
        """
    )
    third_map = {r["unionid"]: r["uid"] for r in cur.fetchall()}
    print(f"third_party union 映射 {len(third_map)}（字段 {third_union}）", flush=True)

    cur.execute(
        f"""
        SELECT
          `{xet_union}` AS unionid,
          MAX(user_id) AS user_id,
          MAX(bind_phone) AS bind_phone
        FROM ys_xet_user_lists
        WHERE `{xet_union}` IS NOT NULL AND `{xet_union}` <> ''
        GROUP BY `{xet_union}`
        """
    )
    xet_map = {
        r["unionid"]: {"user_id": r["user_id"], "bind_phone": r["bind_phone"]}
        for r in cur.fetchall()
    }
    print(f"xet_user_lists union 映射 {len(xet_map)}（字段 {xet_union}）", flush=True)

    cur.execute(f"SELECT id, external_userid FROM `{pay_table}` ORDER BY id")
    bills = cur.fetchall()
    print(f"收款行 {len(bills)}", flush=True)

    rows_out = []
    stats = {
        "total": len(bills),
        "has_external": 0,
        "has_unionid": 0,
        "hit_third": 0,
        "hit_xet": 0,
        "hit_phone": 0,
    }
    for b in bills:
        eid = (b.get("external_userid") or "").strip()
        uid_wx = union_map.get(eid) if eid else None
        third_uid = third_map.get(uid_wx) if uid_wx else None
        xet = xet_map.get(uid_wx) if uid_wx else None
        xet_user_id = xet["user_id"] if xet else None
        bind_phone = xet["bind_phone"] if xet else None
        if eid:
            stats["has_external"] += 1
        if uid_wx:
            stats["has_unionid"] += 1
        if third_uid is not None and str(third_uid) != "":
            stats["hit_third"] += 1
        if xet_user_id is not None and str(xet_user_id) != "":
            stats["hit_xet"] += 1
        if bind_phone is not None and str(bind_phone) != "":
            stats["hit_phone"] += 1
        rows_out.append(
            {
                "id": b["id"],
                "external_userid": eid or None,
                "unionid": uid_wx,
                "third_uid": third_uid,
                "xet_user_id": xet_user_id,
                "bind_phone": bind_phone,
            }
        )

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = EXPORT
    out_dir.mkdir(parents=True, exist_ok=True)
    out_sql = out_dir / f"ys_qywx_pay_bill_enrich_update_{stamp}.sql"
    out_json = out_dir / f"ys_qywx_pay_bill_enrich_update_{stamp}.json"

    need_add_unionid = "unionid" not in pay_cols
    need_add_third = "third_uid" not in pay_cols
    need_add_xet = "xet_user_id" not in pay_cols
    need_add_phone = "bind_phone" not in pay_cols

    with out_sql.open("w", encoding="utf-8") as f:
        f.write("-- READ-ONLY 导出生成；本文件用于在服务器执行更新\n")
        f.write(f"-- source_table={pay_table}\n")
        f.write(f"-- third_union_col={third_union} xet_union_col={xet_union}\n")
        f.write(f"-- stats={stats}\n")
        f.write("SET NAMES utf8mb4;\n")
        f.write("START TRANSACTION;\n\n")

        alters = []
        if need_add_unionid:
            alters.append(
                "ADD COLUMN unionid VARCHAR(64) NULL COMMENT '微信unionid' AFTER external_userid"
            )
        if need_add_third:
            alters.append(
                "ADD COLUMN third_uid VARCHAR(64) NULL COMMENT 'ys_third_party_user.uid' AFTER unionid"
            )
        if need_add_xet:
            alters.append(
                "ADD COLUMN xet_user_id VARCHAR(64) NULL COMMENT 'ys_xet_user_lists.user_id' AFTER third_uid"
            )
        if need_add_phone:
            alters.append(
                "ADD COLUMN bind_phone VARCHAR(32) NULL COMMENT 'ys_xet_user_lists.bind_phone' AFTER xet_user_id"
            )
        if alters:
            f.write(f"ALTER TABLE `{pay_table}`\n  " + ",\n  ".join(alters) + ";\n\n")
        else:
            f.write(f"-- `{pay_table}` 目标字段已存在，跳过 ALTER\n\n")

        # 先清空再写，避免脏值；按 id 精确更新
        f.write(
            f"UPDATE `{pay_table}` SET unionid=NULL, third_uid=NULL, xet_user_id=NULL, bind_phone=NULL;\n\n"
        )

        for r in rows_out:
            f.write(
                f"UPDATE `{pay_table}` SET "
                f"unionid={esc(r['unionid'])}, "
                f"third_uid={esc(r['third_uid'])}, "
                f"xet_user_id={esc(r['xet_user_id'])}, "
                f"bind_phone={esc(r['bind_phone'])} "
                f"WHERE id={esc(r['id'])};\n"
            )

        f.write("\nCOMMIT;\n")
        f.write(
            f"\nSELECT COUNT(*) 总行数,\n"
            f"  SUM(unionid IS NOT NULL AND unionid<>'') 有unionid,\n"
            f"  SUM(third_uid IS NOT NULL AND third_uid<>'') 命中第三方,\n"
            f"  SUM(xet_user_id IS NOT NULL AND xet_user_id<>'') 命中小鹅通,\n"
            f"  SUM(bind_phone IS NOT NULL AND bind_phone<>'') 有手机\n"
            f"FROM `{pay_table}`;\n"
        )

    import json

    out_json.write_text(
        json.dumps({"stats": stats, "rows": rows_out}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    conn.close()

    print("统计:", stats, flush=True)
    print(f"已写(未改库) {out_sql}", flush=True)
    print(f"已写 {out_json}", flush=True)
    print(
        "服务器执行示例:\n"
        f"  mysql -h127.0.0.1 -ujingnao -p db_fz_jingnao < {out_sql.name}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
