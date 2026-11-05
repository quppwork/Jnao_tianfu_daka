"""领域路由：OCR 文本 → solve_* Profile（门面内业务步骤，不进内核 Orchestrator）。"""

from __future__ import annotations

import re

DOMAIN_PROFILE_MAP = {
    "science": "solve_science",
    "language": "solve_language",
    "humanities": "solve_humanities",
    "invention": "solve_invention",
    "arts": "solve_arts",
}

_SCIENCE = re.compile(
    r"数学|物理|化学|生物|方程|函数|导数|积分|向量|电路|力学|酸碱|"
    r"\\frac|\\int|\\sum|\d+\s*[\+\-\×\*÷/=]|勾股|几何|三角",
    re.I,
)
_LANGUAGE = re.compile(
    r"英语|英文|翻译|grammar|vocabulary|reading|完形|听力|单词|时态|定语从句",
    re.I,
)
_HUMANITIES = re.compile(
    r"语文|作文|文言文|古诗|历史|地理|政治|朝代|省会|议论文|阅读理解",
    re.I,
)
_INVENTION = re.compile(
    r"发明|创客|编程|Arduino|机器人|综合实践|STEM|动手做",
    re.I,
)
_ARTS = re.compile(
    r"美术|绘画|素描|音乐|乐理|视唱|色彩|构图|艺术鉴赏",
    re.I,
)


def classify_domain(text: str, *, subject_hint: str | None = None) -> str:
    """返回 domain key：science/language/humanities/invention/arts。"""
    hint = (subject_hint or "").strip()
    blob = f"{hint}\n{text or ''}"
    scores = {
        "science": len(_SCIENCE.findall(blob)),
        "language": len(_LANGUAGE.findall(blob)),
        "humanities": len(_HUMANITIES.findall(blob)),
        "invention": len(_INVENTION.findall(blob)),
        "arts": len(_ARTS.findall(blob)),
    }
    # 提示词强绑定
    hint_l = hint.lower()
    if any(k in hint for k in ("数学", "物理", "化学", "生物", "科学")):
        scores["science"] += 3
    if any(k in hint for k in ("英语", "外语")) or "english" in hint_l:
        scores["language"] += 3
    if any(k in hint for k in ("语文", "历史", "地理", "政治")):
        scores["humanities"] += 3
    if any(k in hint for k in ("发明", "创客", "编程")):
        scores["invention"] += 3
    if any(k in hint for k in ("美术", "音乐", "艺术")):
        scores["arts"] += 3

    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        return "science"  # 默认理科拍题占比最高
    return best[0]


def profile_for_domain(domain: str) -> str:
    return DOMAIN_PROFILE_MAP.get(domain) or "solve_science"
