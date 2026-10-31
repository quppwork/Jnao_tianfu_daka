"""企微同步全链路追踪：批次表 + 行级 created_at/updated_at。

查某次改动:
  SELECT * FROM ys_qywx_sync_run ORDER BY started_at DESC LIMIT 20;
  SELECT * FROM ys_qywx_follow_user WHERE follow_userid='WuShengHua';
  SELECT created_at, updated_at, fetched_at, last_sync_run_id
  FROM ys_qywx_pay_bill WHERE payee_userid='WuShengHua' ORDER BY pay_time DESC LIMIT 20;

created_at = 本行首次入库（上海）；重拉同一单会保留。
updated_at = 本行最后一次被脚本改写（上海）。
fetched_at = 本轮从企微拉到/写库的时间（上海）。
last_sync_run_id → ys_qywx_sync_run.run_id。
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from _wework_paths import now_sh_str

SYNC_RUN_TABLE = "ys_qywx_sync_run"


def ensure_sync_run_table(cur: Any) -> None:
    cur.execute(
        f"""
CREATE TABLE IF NOT EXISTS `{SYNC_RUN_TABLE}` (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id VARCHAR(32) NOT NULL,
  kind VARCHAR(32) NOT NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'running',
  argv TEXT NULL,
  stats_json TEXT NULL,
  error_text VARCHAR(1000) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_run (run_id),
  KEY idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
    )


def start_sync_run(cur: Any, *, kind: str, argv: str = "") -> str:
    ensure_sync_run_table(cur)
    run_id = now_sh_str().replace("-", "").replace(" ", "").replace(":", "") + secrets.token_hex(2)
    cur.execute(
        f"""
        INSERT INTO `{SYNC_RUN_TABLE}`
          (run_id, kind, started_at, status, argv)
        VALUES (%s, %s, %s, 'running', %s)
        """,
        (run_id, kind[:32], now_sh_str(), (argv or "")[:8000]),
    )
    return run_id


def finish_sync_run(
    cur: Any,
    run_id: str,
    *,
    status: str = "ok",
    stats: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if not run_id:
        return
    cur.execute(
        f"""
        UPDATE `{SYNC_RUN_TABLE}`
        SET finished_at=%s, status=%s, stats_json=%s, error_text=%s
        WHERE run_id=%s
        """,
        (
            now_sh_str(),
            status[:16],
            json.dumps(stats, ensure_ascii=False) if stats else None,
            (error or "")[:1000] or None,
            run_id,
        ),
    )
