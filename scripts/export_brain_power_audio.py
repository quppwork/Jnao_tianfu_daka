"""Export talent-tagged audio catalog from local db_fz_jingnao."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "brain_power_audio_catalog.json"
MYSQL = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"

SQL = """
SELECT a.id, c.id, c.title, c.talent,
  a.title, a.sort, a.aliyun_id, a.is_try, a.status
FROM ys_c_av a
JOIN ys_c_course c ON c.id = a.course_id
WHERE c.classify_id = 19
  AND c.talent IN (1, 2, 3, 4, 5)
  AND a.status = 1
  AND a.aliyun_id LIKE '%.mp3'
ORDER BY c.talent, a.sort, a.id;
"""

TALENT_TAG = {1: "学", 2: "思", 3: "行", 4: "德", 5: "赢"}
TALENT_NAME = {1: "学者", 2: "思者", 3: "行者", 4: "德者", 5: "赢者"}


def main() -> None:
    proc = subprocess.run(
        [MYSQL, "-u", "root", "-p1234", "db_fz_jingnao", "--default-character-set=utf8mb4", "-N", "-e", SQL],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    rows: list[dict] = []
    for line in proc.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        talent_code = int(parts[3])
        rows.append(
            {
                "id": int(parts[0]),
                "course_id": int(parts[1]),
                "course_title": parts[2],
                "talent_code": talent_code,
                "talent_tag": TALENT_TAG.get(talent_code, ""),
                "talent_name": TALENT_NAME.get(talent_code, ""),
                "lesson_title": parts[4],
                "lesson_sort": int(parts[5]),
                "play_url": parts[6],
                "is_try": int(parts[7]),
                "status": int(parts[8]),
            }
        )

    counts = dict(Counter(r["talent_tag"] for r in rows))
    payload = {
        "source_database": "db_fz_jingnao",
        "source_tables": ["ys_c_course", "ys_c_av"],
        "classify_id": 19,
        "classify_title": "我知道你是谁",
        "admin_ui_note": "后台「脑力奥秘 > 思/赢/德/行/学」若显示 162 条，可能含线上新增内容；本导出为本地 dump 中五天赋系列 MP3",
        "talent_field_mapping": {
            "ys_c_course.talent": {"1": "学者/学", "2": "思者/思", "3": "行者/行", "4": "德者/德", "5": "赢者/赢"}
        },
        "total": len(rows),
        "counts_by_tag": counts,
        "items": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(rows)} items -> {OUT}")
    print("counts:", counts)


if __name__ == "__main__":
    main()
