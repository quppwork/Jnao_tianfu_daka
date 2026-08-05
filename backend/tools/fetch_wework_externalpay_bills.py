#!/usr/bin/env python3
"""拉取企业微信「对外收款记录」近 N 天，写入独立表。

POST /cgi-bin/externalpay/get_bill_list

用法:
  python -u backend/tools/fetch_wework_externalpay_bills.py --days 5
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
TABLE = "qywx_externalpay_bill"


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


def fetch_bills(token: str, begin_time: int, end_time: int, payee_userid: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = ""
    page = 0
    while True:
        page += 1
        body: dict[str, Any] = {
            "begin_time": begin_time,
            "end_time": end_time,
            "limit": 1000,
        }
        if cursor:
            body["cursor"] = cursor
        if payee_userid:
            body["payee_userid"] = payee_userid
        d = requests.post(
            f"{QYAPI}/externalpay/get_bill_list",
            params={"access_token": token},
            json=body,
            timeout=60,
        ).json()
        err = d.get("errcode", 0)
        if err != 0:
            raise RuntimeError(f"get_bill_list 失败: {d}")
        chunk = d.get("bill_list") or []
        rows.extend(chunk)
        print(f"  page {page}: +{len(chunk)} 累计 {len(rows)}", flush=True)
        if not d.get("next_cursor"):
            # 有的文档用 next_cursor，有的可能没有；无则结束
            # 若返回了 cursor 字段也兼容
            cursor = (d.get("next_cursor") or d.get("cursor") or "").strip()
            if not cursor or not chunk:
                break
        else:
            cursor = str(d.get("next_cursor")).strip()
            if not cursor:
                break
        time.sleep(0.05)
    return rows


def flatten(bill: dict[str, Any]) -> dict[str, Any]:
    commodity = bill.get("commodity_list") or bill.get("commodity")
    commodity_str = None
    if isinstance(commodity, list):
        parts = []
        for c in commodity:
            if isinstance(c, dict):
                parts.append(str(c.get("description") or c.get("name") or c))
            else:
                parts.append(str(c))
        commodity_str = ";".join(parts) if parts else None
    elif commodity is not None:
        commodity_str = str(commodity)
    flat = {
        "transaction_id": bill.get("transaction_id"),
        "out_trade_no": bill.get("out_trade_no"),
        "out_refund_no": bill.get("out_refund_no"),
        "pay_time": bill.get("pay_time"),
        "bill_type": bill.get("bill_type"),
        "trade_state": bill.get("trade_state"),
        "payment_type": bill.get("payment_type"),
        "total_fee": bill.get("total_fee"),
        "total_refund_fee": bill.get("total_refund_fee"),
        "commodity": commodity_str,
        "remark": bill.get("remark"),
        "payee_userid": bill.get("payee_userid"),
        "external_userid": bill.get("external_userid"),
        "mch_id": bill.get("mch_id"),
        "contact_name": (bill.get("contact_info") or {}).get("name"),
        "contact_phone": (bill.get("contact_info") or {}).get("phone"),
        "raw_json": json.dumps(bill, ensure_ascii=False),
    }
    return flat


def write_sql(path: Path, flats: list[dict[str, Any]], begin_time: int, end_time: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ddl = f"""
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS {TABLE};
CREATE TABLE {TABLE} (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  transaction_id VARCHAR(64) NULL,
  out_trade_no VARCHAR(64) NULL,
  out_refund_no VARCHAR(64) NULL,
  pay_time INT UNSIGNED NULL,
  payment_type INT NULL,
  trade_state INT NULL,
  bill_type INT NULL COMMENT '0收款 1退款',
  total_fee BIGINT NULL COMMENT '收款金额(分)',
  total_refund_fee BIGINT NULL COMMENT '退款金额(分)',
  commodity VARCHAR(512) NULL,
  remark VARCHAR(512) NULL,
  payee_userid VARCHAR(64) NULL COMMENT '收款/退款成员',
  external_userid VARCHAR(64) NULL COMMENT '付款人外部联系人',
  mch_id VARCHAR(64) NULL,
  contact_name VARCHAR(128) NULL,
  contact_phone VARCHAR(64) NULL,
  raw_json MEDIUMTEXT NULL,
  range_begin INT UNSIGNED NOT NULL,
  range_end INT UNSIGNED NOT NULL,
  fetched_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_pay_time (pay_time),
  KEY idx_payee (payee_userid),
  KEY idx_external (external_userid),
  KEY idx_tx (transaction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对外收款记录 get_bill_list';
"""
    with path.open("w", encoding="utf-8") as f:
        f.write("-- externalpay/get_bill_list recent days; own table only\n")
        f.write(ddl)
        f.write("SET FOREIGN_KEY_CHECKS=0;\n")
        cols = (
            "transaction_id,out_trade_no,out_refund_no,pay_time,payment_type,trade_state,bill_type,"
            "total_fee,total_refund_fee,commodity,remark,payee_userid,external_userid,mch_id,"
            "contact_name,contact_phone,raw_json,range_begin,range_end,fetched_at"
        )
        for i in range(0, len(flats), 50):
            chunk = flats[i : i + 50]
            vals = []
            for r in chunk:
                vals.append(
                    "("
                    + ",".join(
                        [
                            _esc(r.get("transaction_id")),
                            _esc(r.get("out_trade_no")),
                            _esc(r.get("out_refund_no")),
                            _esc(r.get("pay_time")),
                            _esc(r.get("payment_type")),
                            _esc(r.get("trade_state")),
                            _esc(r.get("bill_type")),
                            _esc(r.get("total_fee")),
                            _esc(r.get("total_refund_fee")),
                            _esc(r.get("commodity")),
                            _esc(r.get("remark")),
                            _esc(r.get("payee_userid")),
                            _esc(r.get("external_userid")),
                            _esc(r.get("mch_id")),
                            _esc(r.get("contact_name")),
                            _esc(r.get("contact_phone")),
                            _esc(r.get("raw_json")),
                            _esc(begin_time),
                            _esc(end_time),
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
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--payee-userid", default="", help="只拉某收款成员；空=全部")
    args = ap.parse_args()

    end = datetime.now()
    begin = end - timedelta(days=args.days)
    begin_time = int(begin.timestamp())
    end_time = int(end.timestamp())
    print(
        f"时间范围: {begin.strftime('%Y-%m-%d %H:%M:%S')} ~ {end.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({begin_time} ~ {end_time})",
        flush=True,
    )

    token = get_token()
    print("拉取 get_bill_list ...", flush=True)
    bills = fetch_bills(token, begin_time, end_time, args.payee_userid)
    flats = [flatten(b) for b in bills]

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = ROOT / "docs" / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"qywx_externalpay_{args.days}d_{stamp}.json"
    out_sql = out_dir / f"qywx_externalpay_{args.days}d_{stamp}.sql"
    out_json.write_text(
        json.dumps(
            {
                "begin_time": begin_time,
                "end_time": end_time,
                "count": len(bills),
                "bill_list": bills,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_sql(out_sql, flats, begin_time, end_time)

    print(f"完成 {len(bills)} 条", flush=True)
    if bills:
        print("样例字段:", sorted(bills[0].keys()), flush=True)
        print("样例:", json.dumps(bills[0], ensure_ascii=False)[:500], flush=True)
    print(f"已写 {out_sql} ({out_sql.stat().st_size // 1024} KB)", flush=True)
    print(f"已写 {out_json}", flush=True)
    print(
        f"导入（只建 {TABLE}）:\n"
        f"  mysql ... db_fz_jingnao < {out_sql.name}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}", file=sys.stderr, flush=True)
        raise SystemExit(1)
