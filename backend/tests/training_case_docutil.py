"""今日修炼实测：按测试用例写文档（一用例一文件）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DOC_ROOT = Path(__file__).resolve().parents[2] / "docs" / "今日修炼实测用例"
TZ8 = timezone(timedelta(hours=8))

CARD_ZH = {
    "wordCount": "字数",
    "time": "用时(分)",
    "accuracy": "准确度(%)",
    "reverseRecite": "倒背",
    "completed": "已完成",
    "correctCount": "正确数",
}


def ensure_doc_root() -> Path:
    DOC_ROOT.mkdir(parents=True, exist_ok=True)
    return DOC_ROOT


def fmt_card(card: dict | None) -> str:
    if not card:
        return "（无）"
    parts = []
    for k, label in CARD_ZH.items():
        if k not in card or card[k] is None:
            continue
        v = card[k]
        if k in ("reverseRecite", "completed"):
            v = "是" if v else "否"
        parts.append(f"{label}={v}")
    return "，".join(parts) if parts else "（无）"


def write_case_doc(
    *,
    case_id: str,
    title: str,
    purpose: str,
    preconditions: list[str],
    steps: list[str],
    expect: list[str],
    actual: dict[str, Any],
    passed: bool,
    detail_tables: list[tuple[str, list[str], list[list[Any]]]] | None = None,
    notes: list[str] | None = None,
) -> Path:
    """写单个用例文档，返回路径。"""
    ensure_doc_root()
    safe = case_id.replace("/", "-")
    path = DOC_ROOT / f"{safe}-{title}.md"
    now = datetime.now(TZ8).strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append(f"# {case_id} {title}")
    lines.append("")
    lines.append(f"> 实跑生成时间：{now}　结果：**{'通过' if passed else '失败'}**")
    lines.append("")
    lines.append("## 用例目的")
    lines.append("")
    lines.append(purpose)
    lines.append("")
    lines.append("## 前置条件")
    lines.append("")
    for p in preconditions:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## 步骤")
    lines.append("")
    for i, s in enumerate(steps, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    lines.append("## 预期")
    lines.append("")
    for e in expect:
        lines.append(f"- {e}")
    lines.append("")
    lines.append("## 实测结果")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    for k, v in actual.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        lines.append(f"| {k} | {v} |")
    lines.append("")
    if detail_tables:
        for t_title, headers, rows in detail_tables:
            lines.append(f"### {t_title}")
            lines.append("")
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")
            for row in rows:
                cells = [str(c).replace("|", "/") for c in row]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    if notes:
        lines.append("## 备注")
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    # 同步机器可读摘要
    meta = {
        "case_id": case_id,
        "title": title,
        "passed": passed,
        "actual": actual,
        "generated_at": now,
    }
    path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def write_catalog(cases: list[dict[str, Any]]) -> Path:
    ensure_doc_root()
    path = DOC_ROOT / "00-用例目录.md"
    lines = [
        "# 今日修炼实测用例目录",
        "",
        "> 每个用例单独成文；本页为索引。由实跑自动维护。",
        "",
        "| 用例编号 | 标题 | 结果 | 文档 |",
        "|---|---|---|---|",
    ]
    for c in cases:
        result = "通过" if c.get("passed") else "失败"
        link = c.get("file", "")
        lines.append(
            f"| {c['case_id']} | {c['title']} | {result} | [{link}]({link}) |"
        )
    lines.append("")
    lines.append("## 覆盖维度")
    lines.append("")
    lines.append("- 时长档：短时 / 标准 / 2–5 小时长训 / 480 超长 / 追加项")
    lines.append("- 完成度：全日打完 / 部分打卡 / 只排课未打卡")
    lines.append("- 选修：多元感知可不打；高效作业/精力恢复免打卡")
    lines.append("- 升段：三日连过、失败清零、升段后新阈值、同日多技能、间隔日连续")
    lines.append("- 学段：小学低/高、初中、高中阈值；字数贴线与用时超时")
    lines.append("- 日切与方案：凌晨 4 点分界、未开始可改时长、已开始禁改")
    lines.append("- 段位聚合：整体=已打卡技能最低；三段捆绑含运算")
    lines.append("- 学员旅程：高效 / 中等 / 低效 多日数据（分文件）")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
