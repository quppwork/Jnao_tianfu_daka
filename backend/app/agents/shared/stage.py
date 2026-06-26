"""学段推断与语言约束 — QA / Guide 等 Agent 共用"""

from __future__ import annotations

STAGE_RULES: dict[str, str] = {
    "primary_low": "学员为小学低年级（1-3年级）：用短句、生活类比，每步 1-2 句话，避免抽象术语。",
    "primary_high": "学员为小学高年级（4-6年级）：分 3-4 步讲解，少公式堆砌，多解释「为什么」。",
    "junior": "学员为初中：可使用概念与公式，讲清考点与常见陷阱。",
    "senior": "学员为高中：推导严谨，可适当压缩铺垫，给出变式思路。",
}


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
