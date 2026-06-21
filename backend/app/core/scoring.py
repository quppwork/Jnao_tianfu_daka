"""评分引擎 — 纯函数，无 I/O"""

from config import load_dimensions


def encode_answer(choice: str) -> int:
    return 1 if choice == "完全符合" else 0


def encode_answers(choices: list[int]) -> str:
    return "".join(str(b) for b in choices)


def calculate_scores(answers: list[int]) -> list[dict]:
    """按维度计算 0-100 得分"""
    dims = load_dimensions()
    result = []
    for dim in dims:
        q_nums = dim["questions"]
        raw = sum(answers[i - 1] for i in q_nums)
        score = round((raw / len(q_nums)) * 100)
        result.append({"key": dim["key"], "name": dim["name"], "label": dim["label"], "score": score})
    return result


def generate_template_summary(scores: list[dict]) -> str:
    """基于得分生成模板摘要"""
    top = max(scores, key=lambda s: s["score"])
    bottom = min(scores, key=lambda s: s["score"])
    mid = sorted(scores, key=lambda s: s["score"])[len(scores) // 2]

    if top["score"] == bottom["score"]:
        return (
            f"各维度得分均为 {top['score']} 分。"
            "建议重新测试以获得更准确的结果，或根据实际情况调整选项。"
        )

    return (
        f"你的优势维度是「{top['label']}」（{top['score']}分），"
        f"表现最为突出。"
        f"「{bottom['label']}」（{bottom['score']}分）有较大成长空间。"
        f"整体来看，「{mid['label']}」处于中等水平。"
        "建议在优势领域继续深耕，同时关注短板维度的提升。"
    )
