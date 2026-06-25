"""学科答疑 Prompt — 学段约束 + 五者天赋教练"""

from __future__ import annotations

STAGE_RULES: dict[str, str] = {
    "primary_low": "学员为小学低年级（1-3年级）：用短句、生活类比，每步 1-2 句话，避免抽象术语。",
    "primary_high": "学员为小学高年级（4-6年级）：分 3-4 步讲解，少公式堆砌，多解释「为什么」。",
    "junior": "学员为初中：可使用概念与公式，讲清考点与常见陷阱。",
    "senior": "学员为高中：推导严谨，可适当压缩铺垫，给出变式思路。",
}

TALENT_COACH: dict[str, str] = {
    "思者": "该学员偏思者：警惕想太多、钻牛角尖。引导先列出「已知/未知」，再一步步验证，提醒「先做完再优化」。",
    "行者": "该学员偏行者：鼓励先动手试一个例子或画图，再从结果反推原理，少空讲理论。",
    "学者": "该学员偏学者：先给清晰定义与结构框架，再解题，帮助建立知识地图。",
    "德者": "该学员偏德者：语气温和，强调过程与努力，避免施压，多肯定已做对的部分。",
    "赢者": "该学员偏赢者：可适当设置小挑战或计时目标，用「闯关」感激发动力。",
}

RAG_KEYWORDS = ("教学法", "课标", "教案", "怎么教", "如何引导", "课程标准", "教学建议")


def infer_school_stage(
    *,
    grade: str | None = None,
    age: int | None = None,
    school_stage: str | None = None,
) -> str:
    if school_stage in STAGE_RULES:
        return school_stage
    g = (grade or "").strip()
    if any(x in g for x in ("一", "二", "三", "1", "2", "3")) and "初" not in g and "高" not in g:
        if any(x in g for x in ("四", "五", "六", "4", "5", "6")):
            return "primary_high"
        return "primary_low"
    if any(x in g for x in ("四", "五", "六", "4", "5", "6")):
        return "primary_high"
    if "初" in g or (age is not None and 12 <= age <= 15):
        return "junior"
    if "高" in g or (age is not None and age >= 16):
        return "senior"
    if age is not None:
        if age <= 9:
            return "primary_low"
        if age <= 12:
            return "primary_high"
        if age <= 15:
            return "junior"
        return "senior"
    return "primary_high"


def talent_coaching_hint(talent_primary: str | None, report_json: dict | None = None) -> str:
    if not talent_primary:
        return "结合学员实际作答情况，耐心分步讲解。"
    base = TALENT_COACH.get(talent_primary.strip(), f"该学员主导天赋为「{talent_primary}」，请结合其特点辅导。")
    if report_json:
        state = (report_json.get("results") or {}).get("State") or {}
        state_name = state.get("name")
        if state_name == "相争" and talent_primary == "思者":
            base += " 当前状态偏「相争」，更易纠结细节，请帮助聚焦题目核心条件。"
    return base


def build_qa_system_prompt(
    *,
    school_stage: str = "primary_high",
    grade: str | None = None,
    age: int | None = None,
    talent_primary: str | None = None,
    report_json: dict | None = None,
    subject: str | None = None,
    rag_context: str | None = None,
    ocr_preview: str | None = None,
) -> str:
    lines = [
        "你是 JNAO 天赋成长平台「知识答题」模块的学科辅导老师「张宇老师」，面向 K12 学生一对一答疑（与首页平台引导对话无关，此处可解题辅导）。",
        "学科范围：数学、语文、英语、科学。",
        "回答要求：先理解问题，再分步讲解；语气亲切；尽量不直接代写作业答案，引导学生思考。",
        STAGE_RULES.get(school_stage, STAGE_RULES["primary_high"]),
    ]
    if grade:
        lines.append(f"年级：{grade}。")
    if age:
        lines.append(f"年龄：{age} 岁。")
    if subject:
        lines.append(f"当前学科：{subject}。")
    lines.append(talent_coaching_hint(talent_primary, report_json))
    if ocr_preview:
        lines.append(f"题目识别预览：{ocr_preview}")
    if rag_context:
        lines.append("以下参考资料供你核对后，用适合学员学段的语言改写回答（不要照抄）：")
        lines.append(rag_context)
    return "\n".join(lines)
