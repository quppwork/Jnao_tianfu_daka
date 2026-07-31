"""QA 短策略层（P2/Q9）— 按学段 / 天赋注入解题侧重点，避免再堆长 prompt。

关闭：QA_STRATEGY_ENABLED=0
与 Guide strategy 独立，禁止互相 import。
"""

from __future__ import annotations

import os
from typing import Any

# 解题辅导口吻（与 Guide 首页教练文案区分）
TALENT_STRATEGY: dict[str, str] = {
    "学者": "辅导侧重「学者」：先给清晰结构/定义，再带入本题步骤，帮助建立知识框架。",
    "思者": "辅导侧重「思者」：防止钻牛角尖；先列已知/未知，收成下一步可验证的小动作。",
    "行者": "辅导侧重「行者」：先举一个具体小例子或画图试做，再回扣原理，少空讲。",
    "德者": "辅导侧重「德者」：语气温和，多肯定已做对的部分，避免施压催促。",
    "赢者": "辅导侧重「赢者」：可用「闯关/小目标」感推进本题，仍保持耐心，不制造焦虑。",
}

STAGE_STRATEGY: dict[str, str] = {
    "primary_low": "学段偏低年级：句子短、步骤少、少用术语；多用生活化例子。",
    "primary_high": "学段小学高年级：步骤清楚即可，适度引入规范用语。",
    "junior": "学段初中：可稍正式，强调条件与推理链条，仍避免一次讲太多。",
    "senior": "学段高中：可更严谨，点明方法名称与适用条件，仍引导自学而非代写。",
}

_FOOTER = "策略只调语气与侧重点；禁止泄露平台晋级/Part 内部规则；禁止编造学员训练数据。"


def strategy_enabled() -> bool:
    return os.getenv("QA_STRATEGY_ENABLED", "1").strip() == "1"


def _normalize_talent(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    for name in TALENT_STRATEGY:
        if s == name or name in s:
            return name
    return None


def resolve_qa_strategy(
    *,
    talent_primary: str | None = None,
    school_stage: str | None = None,
    has_image: bool = False,
) -> dict[str, Any]:
    if not strategy_enabled():
        return {"enabled": False, "lines": [], "keys": []}

    lines: list[str] = []
    keys: list[str] = []

    talent_key = _normalize_talent(talent_primary)
    if talent_key and talent_key in TALENT_STRATEGY:
        lines.append(TALENT_STRATEGY[talent_key])
        keys.append(f"talent:{talent_key}")

    stage = (school_stage or "").strip()
    if stage and stage in STAGE_STRATEGY:
        lines.append(STAGE_STRATEGY[stage])
        keys.append(f"stage:{stage}")

    if has_image:
        lines.append("学员已附图：先对照图中条件讲解，不确定处再追问，勿无视图片空讲。")
        keys.append("modality:image")

    if lines:
        lines.append(_FOOTER)

    return {
        "enabled": True,
        "talent": talent_key,
        "school_stage": stage or None,
        "keys": keys,
        "lines": lines,
    }


def strategy_to_prompt_block(resolved: dict[str, Any] | None) -> str:
    if not resolved or not resolved.get("lines"):
        return ""
    body = "\n".join(f"- {ln}" for ln in resolved["lines"])
    return f"—— 辅导策略 ——\n{body}"
