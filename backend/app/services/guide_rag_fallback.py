"""引导页 RAG 未命中时的固定兜底模板。"""

from __future__ import annotations

from app.agents.guide.context import GuideContext
from app.services.guide_rag_query import (
    extract_guide_skill_focus,
    is_guide_practice_method_question,
)

# 练法类：按技能；{skill} 占位
PRACTICE_MISS_TEMPLATES: dict[str, str] = {
    "超脑阅读": (
        "「超脑阅读」可以先从扫读、抓关键词练起，跟着节奏逐行加速。"
        "具体示范在「今日训练」里，听一遍再练最直观～"
    ),
    "影像追忆": (
        "「影像追忆」重在回忆画面与细节，先从短段落、低压力练起。"
        "打开「今日训练」跟着示范练就好～"
    ),
    "扫描速记": (
        "「扫描速记」先练眼动和抓取关键信息，由短到长逐步加量。"
        "今日训练里有对应示范，去听一听再打卡～"
    ),
    "开口窍": (
        "「开口窍」有配套示范视频，建议先去「今日训练」找到对应项目，"
        "跟着老师示范练一遍再打卡～"
    ),
    "_default": (
        "「{skill}」的具体练法在「今日训练」里有示范，跟着听一遍再练就好。"
        "点下方按钮去今日训练试试～"
    ),
}

TALENT_MISS_TEMPLATE = (
    "关于天赋的详细解读，可以先做或查看「天赋报告」。"
    "若还没测评，点「天赋测试」；已有报告则去「天赋报告」看完整说明～"
)

GENERAL_RAG_MISS_TEMPLATE = (
    "这个问题我暂时没在知识库里找到对应说明。"
    "你可以去「今日训练」看示范，或在「学科答疑」问具体功课～"
)


def build_rag_miss_fallback(message: str, ctx: GuideContext | None) -> str | None:
    """RAG 路由命中但未检索到切片 → 固定模板兜底（不调豆包）。"""
    text = (message or "").strip()
    if not text:
        return None

    skill = extract_guide_skill_focus(text)

    if is_guide_practice_method_question(text):
        if skill and skill in PRACTICE_MISS_TEMPLATES:
            return PRACTICE_MISS_TEMPLATES[skill]
        label = skill or "这项训练"
        return PRACTICE_MISS_TEMPLATES["_default"].replace("{skill}", label)

    if any(k in text for k in ("天赋", "学者", "思者", "赢者", "德者", "行者", "潜能")):
        return TALENT_MISS_TEMPLATE

    if skill and skill in PRACTICE_MISS_TEMPLATES:
        return PRACTICE_MISS_TEMPLATES[skill]

    return GENERAL_RAG_MISS_TEMPLATE
