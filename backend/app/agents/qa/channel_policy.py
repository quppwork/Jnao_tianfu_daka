"""答疑五频道策略 — 软约束进提示词；硬约束供 Harness GateLook / router。

频道：理科 / 文科 / 外语 / 科技 / 书法
旧名（数学/语文/英语/科学/学习心法）经 alias 归一。
"""

from __future__ import annotations

# 旧会话 / 引导跳转 → 新频道
SUBJECT_ALIASES: dict[str, str] = {
    "数学": "理科",
    "语文": "文科",
    "英语": "外语",
    "科学": "科技",
    "学习心法": "书法",
}

CANONICAL_SUBJECTS: tuple[str, ...] = ("理科", "文科", "外语", "科技", "书法")


def normalize_subject(subject: str | None) -> str | None:
    if not subject:
        return None
    text = str(subject).strip()
    if not text:
        return None
    text = SUBJECT_ALIASES.get(text, text)
    return text if text in CANONICAL_SUBJECTS else None


# 软约束：注入 system prompt，引导模型自洽（可被说服绕开，故须配合硬约束）
SOFT_CONSTRAINTS: dict[str, str] = {
    "理科": (
        "【软约束 · 理科频道】\n"
        "- 主战场：数学、物理、化学、生物中的计算/证明/建模题。\n"
        "- 优先步骤化：审题→方法→演算→验算；公式尽量用 LaTeX。\n"
        "- 少写长篇文学赏析或外语精读；若题目明显属其他频道，温和提示切换。"
    ),
    "文科": (
        "【软约束 · 文科频道】\n"
        "- 主战场：语文、历史、政治、哲学向阅读理解、文言、作文思路。\n"
        "- 先通其意再究其法；引用原文作据，不空谈。\n"
        "- 不做整卷数理推导代算；纯外语听说读写请提示切到「外语」。"
    ),
    "外语": (
        "【软约束 · 外语频道】\n"
        "- 主战场：英语（及明确的外语）词汇、语法、翻译、阅读、写作句型。\n"
        "- 像专业英语老师：分步讲解；一套多问时本轮只精讲 1 题，讲完再引导下一题；题号写「第28题」勿写 Q28。\n"
        "- 定位题必须用 > 引用块贴出段落原文，再用表格对照题干与同义改写。\n"
        "- 段落/行号必须能在本会话 OCR 原文中对上；对不上就重读原文或调用 qa_reload_passage，禁止瞎编。\n"
        "- 用户指出定位错误时：重新核对原文并更正，不要让用户重拍搪塞。\n"
        "- 难词用「词：xxx = 中文」单独成行注出；先鼓励再纠正。\n"
        "- 不代写整篇中文作文；纯数理证明题请提示切到「理科」。"
    ),
    "科技": (
        "【软约束 · 科技频道】\n"
        "- 主战场：科学实验、发明创造、脑科学入门、编程/科技现象解释。\n"
        "- 现象→原理→验证；可联系观察与小发明，但不超纲堆砌术语。\n"
        "- 不做书法练字精讲；纯语文赏析/外语精读请提示切频道。"
    ),
    "书法": (
        "【软约束 · 书法频道】\n"
        "- 主战场：书道、练字节奏、定心站桩、学习状态与畏难情绪。\n"
        "- 先定心再下笔；给小到可立刻做的动作，不逼硬扛。\n"
        "- 具体数语外科技题目：安抚后明确建议切换对应频道，不替代精讲。"
    ),
}


# 硬约束摘要：给 GateLook / 产品闸门文案用（真正拦截在 router + product_gate）
HARD_CONSTRAINTS: dict[str, str] = {
    "理科": "硬约束：本频道只承接理科计算/证明/实验数据题；明显外语精读、书法练字、纯文学赏析须拦截并提示切换。",
    "文科": "硬约束：本频道只承接文科阅读/文言/作文思路；明显整卷运算、外语听说主任务须拦截并提示切换。",
    "外语": "硬约束：本频道只承接外语学习任务；明显中文作文主任务、纯数理证明须拦截并提示切换。",
    "科技": "硬约束：本频道只承接科学/发明/科技解释；明显书法练字、纯外语精读须拦截并提示切换。",
    "书法": "硬约束：本频道只承接书道与学习状态；具体学科解题须拦截并提示切换到理科/文科/外语/科技。",
}


def soft_constraint_block(subject: str | None) -> str:
    key = normalize_subject(subject)
    if not key:
        return ""
    return SOFT_CONSTRAINTS.get(key, "")


def hard_constraint_line(subject: str | None) -> str:
    key = normalize_subject(subject)
    if not key:
        return ""
    return HARD_CONSTRAINTS.get(key, "")
