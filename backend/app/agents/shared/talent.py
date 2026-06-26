"""五者天赋教练提示 — QA Agent 共用"""

from __future__ import annotations

TALENT_COACH: dict[str, str] = {
    "思者": "该学员偏思者：警惕想太多、钻牛角尖。引导先列出「已知/未知」，再一步步验证，提醒「先做完再优化」。",
    "行者": "该学员偏行者：鼓励先动手试一个例子或画图，再从结果反推原理，少空讲理论。",
    "学者": "该学员偏学者：先给清晰定义与结构框架，再解题，帮助建立知识地图。",
    "德者": "该学员偏德者：语气温和，强调过程与努力，避免施压，多肯定已做对的部分。",
    "赢者": "该学员偏赢者：可适当设置小挑战或计时目标，用「闯关」感激发动力。",
}


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
