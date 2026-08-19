"""学业规划服务 — 基于训练数据 + AI 生成个性化学业规划报告"""

from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChildUser,
    ContentItem,
    TalentAssessment,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
)
from app.services.assessment_service import get_latest_assessment
from app.services.content_meta import parse_item_meta, skill_from_title
from app.services.doubao_client import chat_completion, is_configured
from app.services.growth_service import get_tier_brief
from app.core.logger import get_logger

logger = get_logger("academic_plan")

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
    
    # 2. 获取总打卡天数和连续天数
    total_checkins = db.scalar(
        select(func.count(func.distinct(TrainingPlan.plan_date)))
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(TrainingPlan.child_user_id == child_user_id)
    ) or 0
    
    # 3. 获取最近30天训练情况
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_checkin_count = db.scalar(
        select(func.count(func.distinct(TrainingPlan.plan_date)))
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date >= thirty_days_ago,
        )
    ) or 0
    recent_checkin_days = recent_checkin_count
    
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
    
    # 5. 获取当前 Tier（从growth_service获取准确值）
    overall_tier = 1
    try:
        tier_brief = get_tier_brief(db, child_user_id)
        overall_tier = tier_brief.get("overall_tier", 1) or 1
    except Exception as e:
        logger.warning(f"Failed to get tier from growth_service, using fallback: {e}")
        # 估算 overall_tier：基于打卡天数
        if total_checkins >= 50:
            overall_tier = 5
        elif total_checkins >= 30:
            overall_tier = 4
        elif total_checkins >= 20:
            overall_tier = 3
        elif total_checkins >= 10:
            overall_tier = 2
        elif total_checkins >= 3:
            overall_tier = 1
    
    # 6. 获取用户信息
    user = db.get(ChildUser, child_user_id)
    grade = None
    nickname = "学员"
    if user:
        nickname = user.nickname or "学员"
        profile = user.profile_json or {}
        grade = profile.get("grade")
    
    return {
        "nickname": nickname,
        "grade": grade,
        "talent_type": talent_type,
        "talent_desc": talent_desc,
        "total_checkins": total_checkins,
        "recent_30d_checkins": recent_checkin_days,
        "overall_tier": overall_tier,
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
    
    system_prompt = """你是JNAO劲脑天赋成长平台的专业学业规划师。请根据学生的训练数据，生成一份专业、鼓励性、可执行的学业规划报告。

要求：
1. 语气积极正面，鼓励学生
2. 分析要具体，基于提供的真实数据
3. 给出可落地的近期（1-2周）、中期（1-2月）、长期（学期）目标
4. 结合学生的天赋类型给出针对性建议
5. 用清晰的分段结构，适合手机阅读
6. 字数控制在500-800字
7. 使用中文输出

报告结构建议：
- 🎯 现状评估（基于训练数据）
- 📈 提分潜力分析
- 📅 学习规划建议（分阶段）
- 💡 天赋优势发挥建议
- 🔥 行动寄语"""

    user_message = f"""请为以下学生生成学业规划报告：

【学生信息】
- 昵称：{data['nickname']}
- 年级：{data['grade'] or '未填写'}
- 天赋类型：{data['talent_type'] or '未测评'}
- 天赋描述：{data['talent_desc'] or '暂无'}

【训练数据】
- 累计打卡：{data['total_checkins']}天
- 近30天打卡：{data['recent_30d_checkins']}天
- 当前段位：第{data['overall_tier']}段

【技能训练情况】
{skills_text}
【提分预测】
{score_text}

请生成一份专业的学业规划报告。"""

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
            "talent_type": data["talent_type"],
            "overall_tier": data["overall_tier"],
            "total_checkins": data["total_checkins"],
        },
        "score_projection": score_proj,
        "skill_stats": data["skill_stats"],
        "report_content": default_report,
        "ai_generated": False,
    }
    
    # 尝试用 AI 生成更个性化的报告
    if is_configured():
        try:
            system_prompt, user_msg = _build_ai_prompt(data, score_proj)
            ai_content = await chat_completion(
                system_prompt=system_prompt,
                user_message=user_msg,
                max_tokens=1200,
                timeout=60,
            )
            if ai_content and len(ai_content.strip()) > 100:
                result["report_content"] = ai_content.strip()
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
    
    # 根据训练情况给出不同的开头
    if checkins == 0:
        opening = f"欢迎{nickname}同学！你即将开启一段精彩的大脑训练之旅。"
        status = "目前你还没有开始训练，建议从今天开始第一次打卡。"
    elif checkins < 7:
        opening = f"很棒！{nickname}同学，你已经迈出了训练的第一步！"
        status = f"你已经完成了{checkins}天训练，继续保持这个势头，7天就能养成一个好习惯。"
    elif checkins < 30:
        opening = f"太棒了！{nickname}同学，你的坚持令人印象深刻！"
        status = f"你已经累计打卡{checkins}天，达到第{tier}段。坚持训练21天以上，大脑已经开始形成新的神经连接！"
    else:
        opening = f"{nickname}同学，你是真正的训练达人！"
        status = f"累计打卡{checkins}天，当前第{tier}段。长期的坚持正在重塑你的大脑能力！"
    
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
    
    if checkins < 3:
        recent_goal += "\n2. 连续打卡满3天，解锁第一段晋升"
        mid_goal = "1. 连续打卡21天，养成训练习惯\n2. 掌握2-3个核心技能的基础方法"
        long_goal = "1. 各技能达到Tier 3以上\n2. 学习效率显著提升，作业时间缩短30%"
    elif tier < 3:
        recent_goal += "\n2. 挑战连续打卡7天\n3. 尝试解锁第二个技能"
        mid_goal = "1. 每个必修技能至少训练10次\n2. 提升至Tier 3"
        long_goal = "1. 核心技能Tier 5+，成为传承特使\n2. 阅读速度、记忆力、计算能力全面提升"
    else:
        recent_goal += "\n2. 保持每周至少5天的训练频率\n3. 挑战高分打卡评价"
        mid_goal = "1. 冲击Tier 5，解锁「劲脑学神」\n2. 将训练技能应用到实际学科学习中"
        long_goal = "1. 冲刺Tier 8-9，成为专利精英\n2. 形成终身受益的高效学习法"
    
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

大脑的可塑性超乎你的想象！每一次专注的训练，都在实实在在地改变你的大脑结构。坚持下去，你会发现：
- 课文背得更快了
- 数学题算得更准了
- 看书注意力更集中了
- 考试做题速度明显提升

从今天开始，每天进步一点点，三个月后你会感谢现在努力的自己！加油！💪"""

    return report
