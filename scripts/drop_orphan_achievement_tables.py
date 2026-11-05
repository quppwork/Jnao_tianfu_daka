# -*- coding: utf-8 -*-
"""Count + DROP orphan achievement/title tables (no ORM in codebase)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql

TABLES = (
    "achievement_definition",
    "achievement_showcase",
    "user_achievement",
    "user_title",
)


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def parse_mysql(url: str) -> dict:
    u = url.replace("mysql+pymysql://", "mysql://")
    p = urlparse(u)
    return {
        "host": p.hostname,
        "port": p.port or 3306,
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "database": (p.path or "/").lstrip("/"),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    # 优先环境变量（可覆盖为线上 RDS）；否则读 backend/.env
    if not (os.environ.get("DATABASE_URL") or "").strip():
        load_env(root / "backend" / ".env")
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL missing")
    cfg = parse_mysql(url)
    print(f"db={cfg['database']} host={cfg['host']}")

    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        connect_timeout=20,
        charset="utf8mb4",
    )
    try:
        cur = conn.cursor()
        print("--- counts ---")
        for t in TABLES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                print(f"{t}: {cur.fetchone()[0]}")
            except Exception as e:
                print(f"{t}: ERR {e}")

        print("--- DROP ---")
        for t in TABLES:
            cur.execute(f"DROP TABLE IF EXISTS `{t}`")
            print(f"dropped {t}")
        conn.commit()

        print("--- verify ---")
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name IN (%s,%s,%s,%s)",
            (cfg["database"], *TABLES),
        )
        left = [r[0] for r in cur.fetchall()]
        print("remaining:", left or "(none)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
