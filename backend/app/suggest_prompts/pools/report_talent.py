"""天赋报告对话 — 20 条轮换（只服务报告页大宇，勿与引导页混用）。

侧重：读本份报告、五者/五维、本天赋练法与职业、知识库可答的体系常识。
占位符 {talent} = 本份报告主天赋。
"""

from __future__ import annotations

from app.suggest_prompts.types import SuggestChip

# 固定 20 条；展示默认抽 4 条轮换
REPORT_TALENT_POOL: tuple[SuggestChip, ...] = (
    SuggestChip("{talent}怎么练", "{talent}怎么练", hot=True),
    SuggestChip("这份报告怎么看", "这份报告怎么看", hot=True),
    SuggestChip("{talent}适合什么职业", "{talent}适合什么职业"),
    SuggestChip("五者是什么", "五者是什么"),
    SuggestChip("报告里的五维怎么看", "这份报告里的五维能量怎么看"),
    SuggestChip("能量状态是什么意思", "报告里的能量状态是什么意思"),
    SuggestChip("{talent}的优势是什么", "{talent}天赋最突出的优势是什么"),
    SuggestChip("{talent}要注意什么", "{talent}天赋在学习上要注意什么"),
    SuggestChip("主副天赋怎么理解", "报告里的主天赋和副天赋怎么理解"),
    SuggestChip("五者分值说明什么", "报告里的五者分值分别说明什么"),
    SuggestChip("{talent}和思者有何不同", "{talent}和思者天赋有什么不同"),
    SuggestChip("怎么跟孩子讲这份报告", "怎么跟孩子讲这份天赋报告比较合适"),
    SuggestChip("报告能指导选专业吗", "这份报告对选专业有什么参考"),
    SuggestChip("执行力低怎么办", "如果报告里执行力偏弱该怎么补"),
    SuggestChip("创新力强怎么用", "报告里创新力较强可以怎么用"),
    SuggestChip("天赋八态是什么", "天赋八态 / 能量状态体系是什么"),
    SuggestChip("相生关系怎么看", "五者相生与关系在报告里怎么看"),
    SuggestChip("学者和赢者差在哪", "学者和赢者天赋差在哪里"),
    SuggestChip("练什么最匹配这份报告", "根据这份报告更该先练哪类能力"),
    SuggestChip("报告结论能当标签吗", "天赋报告结论能不能给孩子贴标签"),
)

assert len(REPORT_TALENT_POOL) == 20
