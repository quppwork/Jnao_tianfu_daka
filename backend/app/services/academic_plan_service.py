"""学业规划服务 — 基于训练数据 + AI 生成个性化学业规划报告"""

from __future__ import annotations

import re
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.shared.stage import STAGE_RULES, infer_school_stage
from app.db.models import (
    ChildUser,
    ContentItem,
    TrainingItem,
    TrainingPlan,
)
from app.services.assessment_service import get_latest_assessment
from app.services.child_training_state import child_grade
from app.services.content_meta import parse_item_meta, skill_from_title
from app.services.doubao_client import chat_completion, is_configured
from app.services.growth_service import get_tier_brief, get_tier_honor, _collect_stats
from app.core.logger import get_logger

logger = get_logger("academic_plan")

_SECTION_RULES = (
    ("status", re.compile(r"现状|评估")),
    ("score", re.compile(r"提分潜力")),
    ("plan", re.compile(r"规划|建议|目标")),
    ("talent", re.compile(r"天赋")),
    ("motto", re.compile(r"寄语")),
)

# 技能名称映射
SKILL_NAMES = {
    "超脑阅读": "超脑阅读",
    "影像追忆": "影像追忆",
    "扫描速记": "扫描速记",
    "极速运算": "极速运算",
    "极速学习": "极速学习",
    "精力恢复": "精力恢复",
    "多元感知": "多元感知",
    "高效作业": "高效作业",
    "数学奥秘": "数学奥秘",
    "英语奥秘": "英语奥秘",
}

# 技能提分估算（基于训练时长和熟练度）
SCORE_PROJECTION = {
    "超脑阅读": {"subject": "语文/英语阅读", "base_boost": 5, "per_tier": 3},
    "影像追忆": {"subject": "记忆力/知识点记忆", "base_boost": 8, "per_tier": 4},
    "扫描速记": {"subject": "阅读速度/审题效率", "base_boost": 6, "per_tier": 3},
    "极速运算": {"subject": "数学计算", "base_boost": 10, "per_tier": 5},
    "极速学习": {"subject": "整体学习效率", "base_boost": 7, "per_tier": 3},
}


def _collect_training_data(db: Session, child_user_id: int) -> dict:
    """收集用户训练数据用于 AI 分析"""
    
    # 1. 获取天赋测评结果
    assessment = get_latest_assessment(db, child_user_id)
    talent_type = None
    talent_desc = None
    if assessment:
        talent_type = assessment.talent_primary
        report_json = assessment.report_json or {}
        talent_desc = (report_json.get("summary") or talent_type or "")
    
    stats = _collect_stats(db, child_user_id)
    total_checkins = stats["checkins"]
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_checkin_days = sum(1 for d in stats["checkin_dates"] if d >= thirty_days_ago)
    
    # 4. 获取各技能训练次数和最近等级
    skill_stats = {}
    items = db.scalars(
        select(ContentItem)
        .join(TrainingItem, TrainingItem.content_item_id == ContentItem.id)
        .join(TrainingPlan, TrainingPlan.id == TrainingItem.plan_id)
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingItem.checkin_status == "done",
        )
    ).all()
    
    for item in items:
        meta = parse_item_meta(item)
        skill = meta.get("skill") or skill_from_title(item.lesson_title)
        if not skill or skill == "训练":
            continue
        
        if skill not in skill_stats:
            skill_stats[skill] = {"count": 0, "total_minutes": 0}
        skill_stats[skill]["count"] += 1
        # 估算时长（从标题或meta中提取，默认10分钟）
        duration = meta.get("duration_minutes") or 10
        skill_stats[skill]["total_minutes"] += duration
    
    # 段位 / 称号只消费 get_tier_brief，与 /tier、成长页进阶之路同一份
    overall_tier = 1
    honor_level = get_tier_honor(1)
    next_title = None
    need = None
    try:
        tier_brief = get_tier_brief(db, child_user_id)
        overall_tier = tier_brief.get("overall_tier", 1) or 1
        honor_level = tier_brief.get("honor_level") or get_tier_honor(overall_tier)
        next_title = tier_brief.get("next_title")
        need = tier_brief.get("need")
    except Exception as e:
        logger.warning(f"Failed to get tier from growth_service, using fallback: {e}")
        honor_level = get_tier_honor(overall_tier)
    
    seven_days_ago = date.today() - timedelta(days=7)
    recent_7d_checkins = sum(1 for d in stats["checkin_dates"] if d >= seven_days_ago)

    user = db.get(ChildUser, child_user_id)
    nickname = "学员"
    grade = None
    age = None
    school_stage = "primary_high"
    if user:
        nickname = user.nickname or "学员"
        pj = user.profile_json if isinstance(user.profile_json, dict) else {}
        learner = pj.get("learner") if isinstance(pj.get("learner"), dict) else {}
        grade = child_grade(user)
        raw_age = pj.get("age") or learner.get("age")
        try:
            age = int(raw_age) if raw_age not in (None, "") else None
        except (TypeError, ValueError):
            age = None
        school_stage = infer_school_stage(
            grade=grade,
            age=age,
            school_stage=pj.get("school_stage") or learner.get("school_stage"),
        )

    return {
        "nickname": nickname,
        "grade": grade,
        "age": age,
        "school_stage": school_stage,
        "talent_type": talent_type,
        "talent_desc": talent_desc,
        "total_checkins": total_checkins,
        "recent_7d_checkins": recent_7d_checkins,
        "recent_30d_checkins": recent_checkin_days,
        "overall_tier": overall_tier,
        "honor_level": honor_level,
        "next_title": next_title,
        "need": need,
        "skill_stats": skill_stats,
    }


def _estimate_score_improvement(data: dict) -> dict:
    """基于训练数据估算分数提升空间"""
    projections = []
    total_estimated = 0
    
    tier = data["overall_tier"]
    skill_stats = data["skill_stats"]
    
    for skill, info in SCORE_PROJECTION.items():
        trained_count = skill_stats.get(skill, {}).get("count", 0)
        if trained_count > 0:
            # 基础分 + 每升一段的加分
            boost = info["base_boost"] + (tier - 1) * info["per_tier"]
            boost = min(boost, 30)  # 单项上限30分
            projections.append({
                "skill": skill,
                "subject": info["subject"],
                "trained_sessions": trained_count,
                "estimated_boost": boost,
            })
            total_estimated += boost
    
    return {
        "items": projections,
        "total_estimated_boost": total_estimated,
    }


def _parse_report_sections(content: str) -> dict[str, str]:
    """把报告拆成前端可点开的完整小节，不截断。"""
    sections: dict[str, list[str]] = {k: [] for k, _ in _SECTION_RULES}
    current: str | None = None
    for raw in (content or "").splitlines():
        line = raw.strip().replace("**", "")
        if not line:
            continue
        heading = (
            line.startswith("#")
            or line.startswith("🎯")
            or line.startswith("📈")
            or line.startswith("📅")
            or line.startswith("💡")
            or line.startswith("🔥")
        )
        mapped = None
        if heading:
            for key, pat in _SECTION_RULES:
                if pat.search(line):
                    mapped = key
                    break
        if mapped:
            current = mapped
            continue
        if current:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def _build_goal_stages(data: dict, score_proj: dict) -> list[dict]:
    total = int(score_proj.get("total_estimated_boost") or 0)
    if total <= 0:
        return []
    third = max(1, round(total / 3))
    two = max(third + 1, round((total * 2) / 3))
    skills = "、".join(list(data.get("skill_stats") or {})[:3]) or "今日必修训练"
    grade = data.get("grade") or "当前年级"
    stage = data.get("school_stage") or "primary_high"
    if stage == "primary_low":
        hints = (
            f"先把每天的{skills}听完、打上卡，像刷牙一样养成习惯。",
            f"练熟一项再加一项，{grade}阶段重在跟得上、做得完。",
            f"能自己读完一小段、算对几道题，就是这个阶段的最高目标。",
        )
    elif stage == "junior":
        hints = (
            f"用{skills}先稳住作业速度，少拖到晚上。",
            f"把训练方法用到错题和预习上，{grade}阶段重在少返工。",
            f"考试前用同样的方法过一遍薄弱科，冲这档提分。",
        )
    elif stage == "senior":
        hints = (
            f"把{skills}嵌进日常刷题节奏，先保证完成量。",
            f"针对薄弱模块加练，{grade}阶段重在正确率。",
            f"用训练提速审题和计算，为综合卷留出检查时间。",
        )
    else:
        hints = (
            f"每天完成{skills}打卡，先拿到基础分。",
            f"连续训练，把方法用到{grade}的作业里。",
            f"冲击更高正确率和速度，挑战这档提分。",
        )
    return [
        {"icon": "zap", "title": "三档提分", "desc": "先拿下基础分", "score": f"1-{third} 分", "hint": hints[0]},
        {"icon": "target", "title": "二档提分", "desc": "再冲一程", "score": f"{third + 1}-{two} 分", "hint": hints[1]},
        {"icon": "trophy", "title": "一档提分", "desc": "挑战最高目标", "score": f"{two + 1}-{total} 分", "hint": hints[2]},
    ]


def _build_ai_prompt(data: dict, score_proj: dict) -> tuple[str, str]:
    """构建 AI 提示词"""
    
    skills_text = ""
    if data["skill_stats"]:
        for skill, stats in data["skill_stats"].items():
            skills_text += f"  - {skill}：训练{stats['count']}次，累计约{stats['total_minutes']}分钟\n"
    else:
        skills_text = "  - 暂未开始技能训练\n"
    
    score_text = ""
    if score_proj["items"]:
        for item in score_proj["items"]:
            score_text += f"  - {item['subject']}：预计可提分{item['estimated_boost']}分（已训练{item['trained_sessions']}次）\n"
    else:
        score_text = "  - 开始训练后将获得个性化提分预测\n"

    stage = data.get("school_stage") or "primary_high"
    stage_rule = STAGE_RULES.get(stage, STAGE_RULES["primary_high"])
    
    system_prompt = f"""你是JNAO劲脑天赋成长平台的学业规划师。根据学生最近训练状态，生成一份可执行的学业规划。

学段约束（必须遵守）：
{stage_rule}
- 建议必须符合该年龄、年级的日常学习，禁止越级（小学低年级不谈中考/高考；小学不布置高中题量）
- 用学生听得懂的词，目标要小、能本周做到
- 必须结合「近7天 / 近30天」训练，不要空喊加油

要求：
1. 语气积极，分析要引用真实打卡和技能数据
2. 近期（1-2周）、中期（1-2月）、长期（本学期）目标分开写，每项目标写具体做什么
3. 结合天赋类型给一条能用上的方法
4. 适合手机阅读；500-800字；中文；段位写「第N段」，不要写 Tier / Lv

必须使用这些小标题（方便前端展开）：
- 🎯 现状评估
- 📈 提分潜力分析
- 📅 学习规划建议
- 💡 天赋优势发挥建议
- 🔥 行动寄语"""

    next_title = data.get("next_title")
    need = data.get("need")
    next_line = "已是最高训练称号"
    if next_title:
        next_line = f"{next_title}（还差{need}阶）" if need else next_title

    age_line = f"{data['age']}岁" if data.get("age") else "未填写"
    user_message = f"""请为以下学生生成学业规划报告：

【学生信息】
- 昵称：{data['nickname']}
- 年级：{data['grade'] or '未填写'}
- 年龄：{age_line}
- 学段：{stage}
- 天赋类型：{data['talent_type'] or '未测评'}
- 天赋描述：{data['talent_desc'] or '暂无'}

【最近训练状态】
- 累计打卡：{data['total_checkins']}天
- 近7天打卡：{data.get('recent_7d_checkins', 0)}天
- 近30天打卡：{data['recent_30d_checkins']}天
- 当前段位：第{data['overall_tier']}段
- 当前称号：{data.get('honor_level') or '新学员'}
- 下一称号：{next_line}

【技能训练情况】
{skills_text}
【提分预测】
{score_text}

请生成符合其年龄和年级的学业规划报告。"""

    return system_prompt, user_message


async def generate_academic_plan(db: Session, child_user_id: int, force_refresh: bool = False) -> dict:
    """生成学业规划报告
    
    Returns:
        dict: 包含报告内容、数据摘要、生成时间等
    """
    # 收集训练数据
    data = _collect_training_data(db, child_user_id)
    score_proj = _estimate_score_improvement(data)
    
    # 默认兜底报告（AI不可用时使用）
    default_report = _generate_default_report(data, score_proj)
    
    result = {
        "generated_at": date.today().isoformat(),
        "student": {
            "nickname": data["nickname"],
            "grade": data["grade"],
            "age": data.get("age"),
            "school_stage": data.get("school_stage"),
            "talent_type": data["talent_type"],
            "overall_tier": data["overall_tier"],
            "honor_level": data.get("honor_level"),
            "total_checkins": data["total_checkins"],
            "recent_7d_checkins": data.get("recent_7d_checkins", 0),
        },
        "score_projection": score_proj,
        "skill_stats": data["skill_stats"],
        "goal_stages": _build_goal_stages(data, score_proj),
        "report_content": default_report,
        "sections": _parse_report_sections(default_report),
        "ai_generated": False,
    }
    
    # 尝试用 AI 生成更个性化的报告
    if is_configured():
        try:
            system_prompt, user_msg = _build_ai_prompt(data, score_proj)
            ai_content = await chat_completion(
                system_prompt=system_prompt,
                user_message=user_msg,
                max_tokens=1600,
                timeout=60,
            )
            if ai_content and len(ai_content.strip()) > 100:
                result["report_content"] = ai_content.strip()
                result["sections"] = _parse_report_sections(ai_content)
                result["ai_generated"] = True
                logger.info(f"Academic plan AI generated for user {child_user_id}")
        except Exception as e:
            logger.warning(f"AI academic plan generation failed: {e}")
    
    return result


def _generate_default_report(data: dict, score_proj: dict) -> str:
    """生成默认兜底报告（不依赖AI）"""
    
    nickname = data["nickname"]
    tier = data["overall_tier"]
    checkins = data["total_checkins"]
    talent = data["talent_type"] or "专属"
    grade = data.get("grade") or ""
    age = data.get("age")
    stage = data.get("school_stage") or "primary_high"
    who = f"{grade}的{nickname}" if grade else nickname
    age_bit = f"{age}岁、" if age else ""
    recent7 = data.get("recent_7d_checkins", 0)

    if checkins == 0:
        opening = f"欢迎{who}同学！按你现在的{age_bit}年级，我们从每天一小步开始。"
        status = "目前还没有开始训练，建议今天完成第一次打卡，先熟悉听音频和打卡步骤。"
    elif checkins < 7:
        opening = f"很棒！{who}同学已经迈出第一步。"
        status = f"已完成{checkins}天训练，近7天打卡{recent7}天。继续保持，满7天就更容易养成习惯。"
    elif checkins < 30:
        opening = f"太棒了！{who}同学的坚持很稳。"
        status = f"累计打卡{checkins}天，近7天{recent7}天，当前第{tier}段。再坚持几周，训练会越来越轻松。"
    else:
        opening = f"{who}同学已经练出节奏了。"
        status = f"累计打卡{checkins}天，近7天{recent7}天，当前第{tier}段。把方法用到这个年级的作业里，进步会更明显。"
    
    # 提分部分
    score_part = ""
    if score_proj["items"]:
        score_part = "\n\n📈 **提分潜力分析**\n\n"
        for item in score_proj["items"]:
            score_part += f"- {item['subject']}：预计可提分 **{item['estimated_boost']}分**（已训练{item['trained_sessions']}次）\n"
        score_part += f"\n通过持续训练，预计整体学科成绩可提升 **{score_proj['total_estimated_boost']}分** 以上！"
    else:
        score_part = "\n\n📈 **提分潜力分析**\n\n开始技能训练后，系统将根据你的训练情况为你预测提分空间。"
    
    # 分阶段建议
    recent_goal = "1. 每天坚持完成今日训练的必修项"
    mid_goal = ""
    long_goal = ""
    
    honor = data.get("honor_level") or get_tier_honor(tier)
    next_title = data.get("next_title")
    need = data.get("need")

    if stage == "primary_low":
        homework = "把今天学的一小段读给家长听，或做完当天练习"
        mid_apply = "能自己读完短文、算对几道口算"
        long_apply = "上课更跟得上，写作业少走神"
    elif stage in ("junior", "senior"):
        homework = "用训练方法完成当天作业里最难的一科"
        mid_apply = "错题当天订正，预习不再从零开始"
        long_apply = "考试留出检查时间，薄弱科少丢基础分"
    else:
        homework = "把训练方法用到当天语文或数学作业"
        mid_apply = "作业更快做完，正确率更稳"
        long_apply = "课堂和考试都更专注"

    if checkins < 3:
        recent_goal += "\n2. 连续打卡满3天，熟悉听音频和打卡"
        mid_goal = f"1. 连续打卡21天，养成习惯\n2. {mid_apply}"
        long_goal = f"1. 各技能达到第3段以上\n2. {long_apply}"
    elif tier < 3:
        recent_goal += f"\n2. 近7天尽量打满5天\n3. {homework}"
        mid_goal = f"1. 每个必修技能至少训练10次\n2. 提升至第3段"
        long_goal = f"1. 核心技能达到第5段以上，成为{get_tier_honor(5)}\n2. {long_apply}"
    else:
        recent_goal += f"\n2. 每周至少5天训练\n3. {homework}"
        if next_title and need:
            mid_goal = f"1. 再进{need}阶，解锁「{next_title}」\n2. {mid_apply}"
        else:
            mid_goal = f"1. 保持「{honor}」\n2. 每周至少5天必修训练"
        long_goal = f"1. 冲刺第8–9段，成为{get_tier_honor(8)}\n2. {long_apply}"
    
    talent_part = ""
    if talent and talent != "未测评":
        talent_part = f"\n\n💡 **{talent}天赋优势发挥**\n\n你的天赋类型是{talent}，建议在训练中重点发挥自己的天赋优势，结合自身特点制定学习策略。"
    else:
        talent_part = "\n\n💡 **天赋优势发挥**\n\n建议先完成天赋测评，了解自己的天赋类型后，系统将为你提供更有针对性的学习建议。"
    
    report = f"""{opening}

🎯 **现状评估**

{status}
你目前处于第{tier}段，正在稳步提升中。每一次打卡都是在为你的大脑升级！{score_part}

📅 **学习规划建议**

**近期目标（1-2周）：**
{recent_goal}

**中期目标（1-2月）：**
{mid_goal}

**长期目标（本学期）：**
{long_goal}{talent_part}

🔥 **行动寄语**

按你现在的年级，每天认真练一小会儿就够。坚持下去，你会发现：
- 读课文更顺
- 口算或作业更快
- 看书更能坐得住
- 课堂上更跟得上

从今天开始，每天进步一点点。加油！"""

    return report
