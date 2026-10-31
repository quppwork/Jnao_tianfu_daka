"""频道路由 — 识别问题所属频道，硬约束检测与当前标签是否一致"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.qa.channel_policy import normalize_subject
from app.agents.qa.subjects.registry import all_subjects

# 关键词/模式：命中越多，该频道得分越高（硬约束检测用）
_SUBJECT_SIGNALS: dict[str, tuple[str, ...]] = {
    "理科": (
        "方程", "函数", "几何", "三角形", "面积", "周长", "体积", "分数", "小数",
        "因式分解", "不等式", "概率", "统计", "导数", "积分", "数列", "证明",
        "直角", "坐标", "平方", "立方", "百分比", "比例", "应用题", "计算",
        "加减", "乘除", "加法", "减法", "乘法", "除法", "余数", "质数", "勾股", "平行", "垂直", "半径", "直径",
        "sin", "cos", "tan", "log", "π", "二次", "一次函数", "勾股定理",
        "物理", "化学", "摩尔", "加速度", "牛顿", "化学方程式", "离子",
    ),
    "文科": (
        "文言文", "古诗", "诗词", "作文", "修辞", "比喻", "拟人", "排比",
        "阅读理解", "概括", "主旨", "段落", "字词", "拼音", "成语", "病句",
        "标点", "赏析", "意象", "默写", "背诵", "实词", "虚词",
        "记叙文", "说明文", "议论文", "人物性格", "环境描写", "中心思想",
        "之乎者也", "对偶", "借代", "夸张", "通感", "炼字",
        "历史", "政治", "唯物", "朝代",
    ),
    "外语": (
        "grammar", "tense", "translate", "translation", "vocabulary", "spelling",
        "pronunciation", "past tense", "present", "future", "clause", "article",
        "pronoun", "adjective", "adverb", "preposition", "时态", "语法", "单词",
        "拼写", "英译", "汉译", "从句", "主谓", "被动语态", "完成时", "进行体",
        "how to say", "what does", "mean in chinese", "mean in english",
        "english", "英语",
    ),
    "科技": (
        "实验", "现象", "生物", "地理", "电路", "电流", "磁场",
        "光合", "呼吸", "生态", "摩擦", "浮力", "物态", "溶解", "元素",
        "发明", "脑科学", "观察", "编程", "代码", "python", "机器人", "科技",
        "传感器", "芯片",
    ),
    "书法": (
        "书法", "书道", "毛笔", "练字", "笔法", "临帖", "站桩", "一天一笔",
        "学习心法", "心态", "焦虑", "畏难", "拖延", "分心", "专注", "定心",
        "浮躁", "压力", "考前紧张", "不想学", "学不进去", "情绪", "复盘习惯",
        "学习状态", "拖延症",
    ),
}

_EN_WORD_RE = re.compile(r"[a-zA-Z]{3,}")
_MATH_EXPR_RE = re.compile(r"\d+\s*[+\-×÷*/=]\s*\d+")
_MIN_SCORE = 2
_MARGIN = 1


@dataclass(frozen=True)
class SubjectMismatch:
    selected: str
    detected: str
    detected_score: int
    selected_score: int


def _score_text(text: str) -> dict[str, int]:
    raw = (text or "").strip()
    lower = raw.lower()
    scores = {s: 0 for s in all_subjects()}
    for subject, signals in _SUBJECT_SIGNALS.items():
        for sig in signals:
            if sig.lower() in lower or sig in raw:
                scores[subject] += 1
    en_hits = len(_EN_WORD_RE.findall(raw))
    if en_hits >= 2:
        scores["外语"] += min(en_hits, 4)
    if _MATH_EXPR_RE.search(raw):
        scores["理科"] += 2
    if re.search(r"[之乎者也焉哉]", raw):
        scores["文科"] += 2
    return scores


def detect_subject(message: str) -> tuple[str | None, int]:
    """返回 (最可能频道, 得分)；得分不足时为 None。"""
    scores = _score_text(message)
    best_subject, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score < _MIN_SCORE:
        return None, best_score
    return best_subject, best_score


def check_subject_mismatch(message: str, selected_subject: str | None) -> SubjectMismatch | None:
    """硬约束：当前频道与问题内容明显不符时返回 mismatch。"""
    selected = normalize_subject(selected_subject)
    if not selected or selected not in all_subjects():
        return None
    scores = _score_text(message)
    selected_score = scores.get(selected, 0)
    detected, detected_score = detect_subject(message)
    if not detected or detected == selected:
        return None
    if detected_score < _MIN_SCORE:
        return None
    if detected_score <= selected_score + _MARGIN:
        return None
    return SubjectMismatch(
        selected=selected,
        detected=detected,
        detected_score=detected_score,
        selected_score=selected_score,
    )


def mismatch_reply(mismatch: SubjectMismatch) -> str:
    return (
        f"同学，这道题看起来更像是「{mismatch.detected}」频道的问题，"
        f"而你当前选的是「{mismatch.selected}」。"
        f"请先点顶部切换到「{mismatch.detected}」，再重新提问，"
        f"这样对应导师才能用合适的方法帮你讲解哦～"
    )
