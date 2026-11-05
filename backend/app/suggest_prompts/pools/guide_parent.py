"""家长引导页 — 30 条轮换（家长大宇，勿与报告/孩子池混用）。

侧重：读孩子报告、家长课堂、提分营、陪伴话术、训练看板。
"""

from __future__ import annotations

from app.suggest_prompts.types import SuggestChip

GUIDE_PARENT_POOL: tuple[SuggestChip, ...] = (
    SuggestChip("学者天赋是什么", "学者天赋是什么"),
    SuggestChip("思者天赋是什么", "思者天赋是什么"),
    SuggestChip("行者天赋是什么", "行者天赋是什么"),
    SuggestChip("德者天赋是什么", "德者天赋是什么"),
    SuggestChip("赢者天赋是什么", "赢者天赋是什么"),
    SuggestChip("五者天赋怎么分", "五者天赋是怎么划分的"),
    SuggestChip("孩子报告怎么看", "孩子的天赋报告该怎么解读"),
    SuggestChip("怎么跟孩子讲报告", "怎么跟孩子讲天赋报告比较合适"),
    SuggestChip("家长课堂是什么", "家长课堂是什么，有哪些课"),
    SuggestChip("什么是火箭提分营", "什么是火箭提分营"),
    SuggestChip("提分营适合谁", "火箭提分营适合什么样的孩子"),
    SuggestChip("提分营怎么收费", "火箭提分营的服务周期和收费是怎样的"),
    SuggestChip("孩子今天练了吗", "孩子今天的训练完成了吗"),
    SuggestChip("孩子连续打卡怎样", "孩子最近连续打卡情况怎么样"),
    SuggestChip("孩子主导天赋是什么", "孩子的主导天赋是什么"),
    SuggestChip("厌学怎么按天赋看", "孩子厌学，从五者天赋怎么理解"),
    SuggestChip("青春期怎么陪伴", "青春期孩子按天赋该怎么陪伴"),
    SuggestChip("选专业要不要按天赋", "选专业要不要参考五者天赋"),
    SuggestChip("学者家长要注意什么", "学者型孩子家长要注意什么"),
    SuggestChip("思者灵感多怎么办", "思者孩子点子多但落不了地怎么办"),
    SuggestChip("行者坐不住怎么办", "行者孩子坐不住、爱动怎么办"),
    SuggestChip("德者太在意评价", "德者孩子太在意别人评价怎么办"),
    SuggestChip("赢者好胜怎么引导", "赢者孩子好胜心强怎么引导"),
    SuggestChip("开口窍对家长有用吗", "开口窍训练对家长沟通有帮助吗"),
    SuggestChip("超脑阅读家长怎么配合", "孩子练超脑阅读时家长怎么配合"),
    SuggestChip("报告和成绩啥关系", "天赋报告和考试成绩是什么关系"),
    SuggestChip("要不要逼孩子练", "孩子不想练，家长要不要逼"),
    SuggestChip("一键咨询找谁", "想找真人老师咨询该怎么进"),
    SuggestChip("家长课堂先听哪课", "家长课堂建议先听哪一类课"),
    SuggestChip("怎么判断孩子是哪者", "怎么初步判断孩子更像五者里的哪一类"),
)

assert len(GUIDE_PARENT_POOL) == 30
