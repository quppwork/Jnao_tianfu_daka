"""Guide 查询归一（R4）— 同义 / 高频错字 / 共现补短语，供工具调度使用。"""

from __future__ import annotations

# 同义 → 词表已有关键词
_SYNONYM_TO_CANON: tuple[tuple[str, str], ...] = (
    ("打卡数值", "打卡内容"),
    ("具体数值", "打卡内容"),
    ("填了啥", "填了什么"),
    ("练了啥", "练了什么"),
    ("上次的打卡", "上次打卡"),
    ("上一次的打卡", "上一次打卡"),
    ("最近一回", "最近一次"),
    ("下一级别", "下一等级"),
    ("升一级", "下一等级"),
    ("怎么升级", "怎么晋级"),
    ("如何升级", "如何晋级"),
    ("课表怎么排", "方案怎么排"),
    ("今日课表", "今日安排"),
)

# 高频错字 / 形近（刻意短表，避免误伤）
_TYPO_TO_CANON: tuple[tuple[str, str], ...] = (
    ("打卡内同", "打卡内容"),
    ("打卡详请", "打卡详情"),
    ("记禄", "记录"),
    ("打卡记绿", "打卡记录"),
    ("近一次", "最近一次"),
    ("练级", "等级"),
)

# 两词共现（可不连续）→ 补上规范短语，供子串启发式命中
_COOC_TO_PHRASE: tuple[tuple[tuple[str, str], str], ...] = (
    (("打卡", "内容"), "打卡内容"),
    (("打卡", "详情"), "打卡详情"),
    (("打卡", "数值"), "打卡内容"),
    (("最近", "打卡"), "最近一次"),
    (("上次", "打卡"), "上次打卡"),
    (("训练", "方案"), "训练方案"),
    (("方案", "怎么排"), "方案怎么排"),
    (("下一", "等级"), "下一等级"),
    (("怎么", "晋级"), "怎么晋级"),
)

_BUSINESS_HINTS: tuple[str, ...] = (
    "打卡",
    "训练",
    "天赋",
    "测评",
    "报告",
    "等级",
    "晋级",
    "档位",
    "方案",
    "进度",
    "练",
    "字数",
    "用时",
    "备注",
    "历史",
    "今天",
    "今日",
    "最近",
    "上次",
)


def normalize_guide_query(message: str) -> str:
    """返回调度用文本：原句 + 归一补丁（不删原词，只追加/替换已知噪声）。"""
    raw = (message or "").strip()
    if not raw:
        return ""
    text = raw
    for src, dst in _TYPO_TO_CANON:
        if src in text:
            text = text.replace(src, dst)
    for src, dst in _SYNONYM_TO_CANON:
        if src in text and dst not in text:
            text = text.replace(src, dst)
    extras: list[str] = []
    for (a, b), phrase in _COOC_TO_PHRASE:
        if a in text and b in text and phrase not in text:
            extras.append(phrase)
    if extras:
        text = f"{text} {' '.join(extras)}"
    return text


def looks_like_business_query(message: str) -> bool:
    """归一后仍像业务问句（非纯闲聊）→ 可触发二次规划。"""
    text = normalize_guide_query(message)
    if not text:
        return False
    return any(k in text for k in _BUSINESS_HINTS)


def looks_like_needs_clarify(message: str) -> bool:
    """缺关键槽位、宜先澄清（R3）。"""
    text = normalize_guide_query(message)
    if not text:
        return False
    # 「那天/某天」无具体日期
    if any(k in text for k in ("那天", "某天", "哪天", "哪一日")) and not any(
        ch.isdigit() for ch in text
    ):
        return True
    # 「哪个」技能/项目但未点名
    if "哪个" in text and any(k in text for k in ("技能", "项目", "课", "训练")):
        if not any(
            k in text
            for k in ("超脑", "影像", "扫描", "极速", "阅读", "运算", "学习", "感知")
        ):
            return True
    return False
