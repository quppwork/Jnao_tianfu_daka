"""孩子引导页 — 30 条轮换（学生大宇首页，勿与报告/家长池混用）。

侧重：练法、今日训练、五者常识、平台入口；语气面向孩子。
"""

from __future__ import annotations

from app.suggest_prompts.types import SuggestChip

GUIDE_CHILD_POOL: tuple[SuggestChip, ...] = (
    SuggestChip("学者天赋是什么", "学者天赋是什么"),
    SuggestChip("思者天赋是什么", "思者天赋是什么"),
    SuggestChip("行者天赋是什么", "行者天赋是什么"),
    SuggestChip("德者天赋是什么", "德者天赋是什么"),
    SuggestChip("赢者天赋是什么", "赢者天赋是什么"),
    SuggestChip("五者是怎么分的", "五者天赋是怎么划分的"),
    SuggestChip("超脑阅读怎么练", "超脑阅读怎么练"),
    SuggestChip("开口窍是什么", "开口窍是什么"),
    SuggestChip("开口窍怎么练", "开口窍怎么练"),
    SuggestChip("影像追忆怎么练", "影像追忆怎么练"),
    SuggestChip("扫描速记要点", "扫描速记的训练要点是什么"),
    SuggestChip("极速运算怎么练", "极速运算怎么练"),
    SuggestChip("今天练什么", "我今天的训练计划是什么"),
    SuggestChip("我测过天赋了吗", "我测过天赋了吗"),
    SuggestChip("我的天赋是什么", "我的主导天赋是什么"),
    SuggestChip("连续打卡有什么用", "连续打卡有什么用"),
    SuggestChip("段位怎么升", "训练段位怎么升"),
    SuggestChip("什么是火箭提分营", "什么是火箭提分营"),
    SuggestChip("提分营适合谁", "火箭提分营适合什么样的孩子"),
    SuggestChip("学者怎么学语文", "学者天赋学语文有什么方法"),
    SuggestChip("思者怎么学数学", "思者天赋学数学怎么提升"),
    SuggestChip("赢者练什么合适", "赢者天赋更适合练哪些项目"),
    SuggestChip("行者容易分心怎么办", "行者孩子容易分心怎么办"),
    SuggestChip("德者怎么沟通", "德者天赋在沟通上有什么特点"),
    SuggestChip("左右脑平衡是什么", "报告里说的左右脑平衡是什么意思"),
    SuggestChip("专注99是什么", "天赋里的「专注99」是什么意思"),
    SuggestChip("去学科答疑做什么", "学科答疑里可以问什么"),
    SuggestChip("今日训练打卡了吗", "我今天训练打卡了吗"),
    SuggestChip("能量不够了怎么办", "训练能量不够了怎么办"),
    SuggestChip("怎么开始第一次测评", "我还没测天赋，应该怎么开始"),
)

assert len(GUIDE_CHILD_POOL) == 30
