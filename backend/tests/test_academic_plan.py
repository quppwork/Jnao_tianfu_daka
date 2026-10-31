"""学业规划：学段约束、小节拆分、提分档提示"""

from app.services.academic_plan_service import (
    _build_ai_prompt,
    _build_goal_stages,
    _parse_report_sections,
)


def test_parse_report_keeps_full_plan_not_first_line_only():
    text = """🎯 **现状评估**

你已经完成了3天训练，继续保持这个势头，7天就能养成一个好习惯。

📅 **学习规划建议**

**近期目标（1-2周）：**
1. 每天坚持完成今日训练的必修项
2. 连续打卡满3天

🔥 **行动寄语**

大脑的可塑性超乎你的想象！每一次专注的训练，都在实实在在地改变结构。
"""
    sections = _parse_report_sections(text)
    assert "3天训练" in sections["status"]
    assert "每天坚持完成今日训练" in sections["plan"]
    assert "连续打卡满3天" in sections["plan"]
    assert "可塑性" in sections["motto"]


def test_ai_prompt_includes_age_grade_and_stage_rule():
    data = {
        "nickname": "小明",
        "grade": "二年级",
        "age": 8,
        "school_stage": "primary_low",
        "talent_type": "学者",
        "talent_desc": "",
        "total_checkins": 3,
        "recent_7d_checkins": 2,
        "recent_30d_checkins": 3,
        "overall_tier": 1,
        "honor_level": "传承特使",
        "next_title": "劲脑学神",
        "need": 4,
        "skill_stats": {"超脑阅读": {"count": 2, "total_minutes": 20}},
    }
    system, user = _build_ai_prompt(data, {"items": [], "total_estimated_boost": 0})
    assert "二年级" in user
    assert "8岁" in user
    assert "近7天" in user
    assert "小学低年级" in system
    assert "中考" in system or "高考" in system
    assert "第N段" in system


def test_goal_stages_primary_low_avoids_exam_talk():
    stages = _build_goal_stages(
        {
            "grade": "一年级",
            "school_stage": "primary_low",
            "skill_stats": {"超脑阅读": {"count": 1}},
        },
        {"total_estimated_boost": 13},
    )
    assert len(stages) == 3
    blob = "".join(s["hint"] for s in stages)
    assert "高考" not in blob
    assert "一年级" in blob or "习惯" in blob
