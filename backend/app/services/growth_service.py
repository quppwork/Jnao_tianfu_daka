"""成长里程碑 — 徽章、荣誉级别、时间线、分享（基于真实业务数据聚合）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, ContentItem, QaMessage, QaSession, TalentAssessment, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import get_latest_assessment, resolve_effective_talent
from app.services.chat_archive_service import earliest_qa_created_at
from app.services.content_meta import parse_item_meta, skill_from_title
from app.services.qa_service import count_user_messages

# 全能王者：至少完成打卡的核心能力课（与课表首屏能力对齐）
MASTERY_SKILLS = ("影像追忆", "扫描速记", "极速学习", "数学奥秘", "英语奥秘")

CHECKIN_MILESTONES = (1, 7, 10, 30, 100)
QA_MILESTONES = (1, 10, 50, 100)

# 🆕 v2.0 九阶荣誉体系：按 overall_tier 映射头衔
def get_tier_honor(overall_tier: int) -> str:
    """将整体 Tier 映射为荣誉头衔。

    Tier 1-4: 传承特使
    Tier 5-7: 劲脑学神
    Tier 8-9: 专利精英
    """
    if overall_tier >= 8:
        return "专利精英"
    if overall_tier >= 5:
        return "劲脑学神"
    if overall_tier >= 1:
        return "传承特使"
    return "新学员"


def _checkin_count(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0


def _checkin_dates(db: Session, child_user_id: int) -> list[date]:
    rows = db.scalars(
        select(TrainingPlan.plan_date)
        .join(TrainingRecord, TrainingRecord.plan_id == TrainingPlan.id)
        .where(TrainingPlan.child_user_id == child_user_id)
        .distinct()
        .order_by(TrainingPlan.plan_date.asc())
    ).all()
    return list(rows)


def _checkin_streak(dates: list[date], *, today: date | None = None) -> int:
    if not dates:
        return 0
    today = today or date.today()
    date_set = set(dates)
    # 允许今天未打卡但从昨天起的连续 streak
    start = today if today in date_set else today - timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    cursor = start
    while cursor in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _trained_skills(db: Session, child_user_id: int) -> set[str]:
    items = db.scalars(
        select(ContentItem)
        .join(TrainingItem, TrainingItem.content_item_id == ContentItem.id)
        .join(TrainingPlan, TrainingPlan.id == TrainingItem.plan_id)
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingItem.checkin_status == "done",
        )
    ).all()
    skills: set[str] = set()
    for item in items:
        meta = parse_item_meta(item)
        skill = meta.get("skill") or skill_from_title(item.lesson_title)
        if skill and skill != "训练":
            skills.add(skill)
    return skills


def _mastery_complete(trained: set[str]) -> bool:
    return all(s in trained for s in MASTERY_SKILLS)


def _collect_stats(db: Session, child_user_id: int) -> dict:
    assessment = get_latest_assessment(db, child_user_id)
    checkins = _checkin_count(db, child_user_id)
    dates = _checkin_dates(db, child_user_id)
    streak = _checkin_streak(dates)
    qa_count = count_user_messages(db, child_user_id)
    trained = _trained_skills(db, child_user_id)
    mastery = _mastery_complete(trained)
    user = db.get(ChildUser, child_user_id)
    return {
        "user": user,
        "assessment": assessment,
        "checkins": checkins,
        "checkin_dates": dates,
        "streak": streak,
        "qa_count": qa_count,
        "trained_skills": trained,
        "mastery": mastery,
    }


def _event_date_str(d: date) -> str:
    return d.strftime("%m-%d")


def get_badges(db: Session, child_user_id: int, stats: dict | None = None) -> list[dict]:
    if stats is None:
        stats = _collect_stats(db, child_user_id)
    trained = stats["trained_skills"]
    mastery = stats["mastery"]
    earned_at_map = _build_earned_at_map(db, child_user_id, stats)

    defs = [
        ("首次测评", "🌟", "完成天赋测试", stats["assessment"] is not None, "assessment"),
        ("初露锋芒", "🔥", "累计打卡 7 次", stats["checkins"] >= 7, "checkin_7"),
        ("持之以恒", "⚡", "累计打卡 30 次", stats["checkins"] >= 30, "checkin_30"),
        ("百炼成钢", "🏆", "累计打卡 100 次", stats["checkins"] >= 100, "checkin_100"),
        ("连续一周", "📅", "连续打卡 7 天", stats["streak"] >= 7, "streak_7"),
        ("答疑新星", "💬", "首次学科提问", stats["qa_count"] >= 1, "qa_1"),
        ("知识达人", "💎", "累计提问 100 次", stats["qa_count"] >= 100, "qa_100"),
        ("全能王者", "👑", "完成全部核心能力训练", mastery, "mastery"),
    ]
    progress_map = {
        "checkin_7": f"{min(stats['checkins'], 7)}/7",
        "checkin_30": f"{min(stats['checkins'], 30)}/30",
        "checkin_100": f"{min(stats['checkins'], 100)}/100",
        "streak_7": f"{min(stats['streak'], 7)}/7",
        "qa_100": f"{min(stats['qa_count'], 100)}/100",
        "mastery": f"{sum(1 for s in MASTERY_SKILLS if s in trained)}/{len(MASTERY_SKILLS)}",
    }
    out = []
    for name, icon, cond, earned, key in defs:
        item = {
            "name": name,
            "icon": icon,
            "cond": cond,
            "earned": earned,
            "earned_at": earned_at_map.get(key) if earned else None,
        }
        if key in progress_map and not earned:
            item["progress"] = progress_map[key]
        out.append(item)
    return out


def _build_earned_at_map(db: Session, child_user_id: int, stats: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    assessment = stats["assessment"]
    if assessment and assessment.assessed_at:
        mapping["assessment"] = assessment.assessed_at.date().isoformat()

    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    for i, rec in enumerate(records, start=1):
        if i == 7:
            mapping["checkin_7"] = _record_date_iso(rec)
        if i == 30:
            mapping["checkin_30"] = _record_date_iso(rec)
        if i == 100:
            mapping["checkin_100"] = _record_date_iso(rec)

    if stats["qa_count"] >= 1:
        first_qa_at = earliest_qa_created_at(db, child_user_id)
        if first_qa_at:
            mapping["qa_1"] = first_qa_at.date().isoformat()

    if stats["streak"] >= 7:
        mapping["streak_7"] = date.today().isoformat()

    if stats["mastery"]:
        mapping["mastery"] = date.today().isoformat()

    return mapping


def _record_date_iso(rec: TrainingRecord) -> str:
    if rec.created_at:
        return rec.created_at.date().isoformat()
    return date.today().isoformat()


def get_milestones(db: Session, child_user_id: int, stats: dict | None = None) -> list[dict]:
    """🆕 v2.0 九阶荣誉体系 — 三段头衔，按 overall_tier 判定达成状态"""
    if stats is None:
        stats = _collect_stats(db, child_user_id)
    user = stats["user"]

    # 获取 overall_tier
    overall_tier = 1
    try:
        from app.services.child_training_state import get_training_progress, overall_tier as _calc_tier
        if user:
            state = get_training_progress(user)
            overall_tier = _calc_tier(state)
    except Exception:
        import logging
        logging.getLogger("jnao").warning("growth: 计算 overall_tier 失败，退回默认", exc_info=True)

    return [
        {
            "level": "传承特使",
            "condition": "基础训练阶段",
            "achieved": overall_tier >= 1,
            "progress": "已达成 ✓" if overall_tier >= 1 else "未开始训练",
        },
        {
            "level": "劲脑学神",
            "condition": "进阶训练阶段",
            "achieved": overall_tier >= 5,
            "progress": "已达成 ✓" if overall_tier >= 5 else "继续努力中",
        },
        {
            "level": "专利精英",
            "condition": "高阶关门弟子",
            "achieved": overall_tier >= 8,
            "progress": "已达成 ✓" if overall_tier >= 8 else "继续努力中",
        },
    ]


def get_timeline(db: Session, child_user_id: int, limit: int = 40, stats: dict | None = None) -> list[dict]:
    if stats is None:
        stats = _collect_stats(db, child_user_id)
    events: list[dict] = []

    assessment = db.scalar(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.asc())
        .limit(1)
    )
    if assessment:
        d = assessment.assessed_at.date() if assessment.assessed_at else date.today()
        events.append({
            "type": "assessment",
            "title": "完成首次天赋测评",
            "date": _event_date_str(d),
            "desc": f"主导天赋：{assessment.talent_primary or '未知'}",
            "done": True,
            "sort_key": d.isoformat(),
        })

    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    for i, rec in enumerate(records, start=1):
        if i not in CHECKIN_MILESTONES:
            continue
        d = rec.created_at.date() if rec.created_at else date.today()
        events.append({
            "type": "checkin",
            "title": f"第 {i} 次打卡",
            "date": _event_date_str(d),
            "desc": "完成今日训练打卡",
            "done": True,
            "sort_key": d.isoformat() + f"-c{i:04d}",
        })

    if stats["streak"] >= 7:
        events.append({
            "type": "streak",
            "title": "连续打卡 7 天",
            "date": _event_date_str(date.today()),
            "desc": "养成稳定训练习惯",
            "done": True,
            "sort_key": date.today().isoformat() + "-streak7",
        })

    for skill in sorted(stats["trained_skills"] & set(MASTERY_SKILLS)):
        events.append({
            "type": "skill",
            "title": f"首次完成「{skill}」训练",
            "date": "已达成",
            "desc": "核心能力训练进度 +1",
            "done": True,
            "sort_key": f"skill-{skill}",
        })

    first_qa_at = earliest_qa_created_at(db, child_user_id)
    if first_qa_at:
        d = first_qa_at.date()
        events.append({
            "type": "qa",
            "title": "首次学科答疑",
            "date": _event_date_str(d),
            "desc": "提出第一个学科问题",
            "done": True,
            "sort_key": d.isoformat() + "-qa1",
        })

    qa_count = stats["qa_count"]
    for n in QA_MILESTONES:
        if n == 1 or qa_count < n:
            continue
        events.append({
            "type": "qa",
            "title": f"累计提问 {n} 次",
            "date": "已达成",
            "desc": "坚持向张宇老师请教",
            "done": True,
            "sort_key": f"qa-milestone-{n:04d}",
        })

    checkins = stats["checkins"]
    future_goals = [
        (30, "累计打卡 30 次", "解锁「持之以恒」徽章"),
        (100, "累计打卡 100 次", "解锁「百炼成钢」金徽章"),
    ]
    if not stats["mastery"]:
        future_goals.append((0, "完成全部核心能力训练", "解锁「全能王者」徽章"))
    for threshold, title, desc in future_goals:
        if threshold and checkins >= threshold:
            continue
        events.append({
            "type": "goal",
            "title": title,
            "date": "未来",
            "desc": desc,
            "done": False,
            "sort_key": f"z-future-{threshold}",
        })

    events.sort(key=lambda e: e["sort_key"])
    for e in events:
        e.pop("sort_key", None)
    return events[:limit]


def get_calendar_days(db: Session, child_user_id: int) -> list[dict]:
    """按天聚合孩子每天的活动明细（打卡、完成的训练课、提问、测评）。

    返回按日期升序的列表，每天一条：{"date": "YYYY-MM-DD", "items": [{type, title, icon}]}
    """
    from collections import defaultdict

    days: dict[str, list[dict]] = defaultdict(list)

    def _key(d: date) -> str:
        return d.isoformat()

    # 1) 打卡 + 完成的训练课（列出每一个完成的具体训练项）
    records = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.asc())
    ).all()
    item_ids = {r.item_id for r in records if r.item_id}
    items_by_id: dict[int, TrainingItem] = {}
    content_ids: set[int] = set()
    if item_ids:
        rows = db.scalars(select(TrainingItem).where(TrainingItem.id.in_(item_ids))).all()
        items_by_id = {it.id: it for it in rows}
        content_ids = {it.content_item_id for it in rows if it.content_item_id}
    
    # 获取ContentItem的标题
    content_by_id: dict[int, ContentItem] = {}
    if content_ids:
        c_rows = db.scalars(select(ContentItem).where(ContentItem.id.in_(content_ids))).all()
        content_by_id = {c.id: c for c in c_rows}

    added_titles: dict[str, set[str]] = defaultdict(set)  # 按日期去重
    for rec in records:
        d = _key(rec.train_date if rec.train_date else (rec.created_at.date() if rec.created_at else date.today()))
        it = items_by_id.get(rec.item_id)
        if it and it.checkin_status == "done":
            # 获取训练项标题：优先用TrainingItem.title，其次用ContentItem.lesson_title
            title = it.title
            if not title and it.content_item_id:
                ci = content_by_id.get(it.content_item_id)
                if ci:
                    title = ci.lesson_title
            if not title:
                title = "完成一项训练"
            
            # 去重：同一天同一标题只加一次
            if title not in added_titles[d]:
                added_titles[d].add(title)
                days[d].append({"type": "skill", "title": title, "icon": "brain"})

    # 2) 提问（孩子的提问消息，每天最多展示 3 条最新）
    # 只查需要的列：qa_message 可能有历史库缺 image_url 列，整表查询会报错
    msgs = db.execute(
        select(QaMessage.id, QaMessage.content, QaMessage.created_at)
        .join(QaSession, QaSession.id == QaMessage.session_id)
        .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
        .order_by(QaMessage.id.desc())
    ).all()
    qa_count: dict[str, int] = defaultdict(int)
    for m in msgs:
        if not m.created_at:
            continue
        d = _key(m.created_at.date())
        text = (m.content or "").strip()
        if not text:
            continue
        qa_count[d] += 1
        if qa_count[d] <= 3:
            days[d].append({"type": "qa", "title": text[:50], "icon": "message"})

    # 3) 天赋测评
    assessments = db.scalars(
        select(TalentAssessment)
        .where(TalentAssessment.child_user_id == child_user_id)
        .order_by(TalentAssessment.id.asc())
    ).all()
    for a in assessments:
        if not a.assessed_at:
            continue
        d = _key(a.assessed_at.date())
        if not any(e["type"] == "assessment" for e in days[d]):
            days[d].append({"type": "assessment", "title": "完成天赋测评", "icon": "star"})

    return [{"date": d, "items": items} for d, items in sorted(days.items())]


def get_summary(db: Session, child_user_id: int, stats: dict | None = None) -> dict:
    if stats is None:
        stats = _collect_stats(db, child_user_id)
    badges = get_badges(db, child_user_id, stats=stats)
    earned = sum(1 for b in badges if b["earned"])
    milestones = get_milestones(db, child_user_id, stats=stats)
    # 🆕 v2.0: 荣誉头衔优先按九阶 Tier 判定，回退到打卡里程碑
    overall_tier = 1
    try:
        from app.services.child_training_state import get_training_progress, overall_tier as _overall_tier
        user = stats["user"]
        if user:
            state = get_training_progress(user)
            overall_tier = _overall_tier(state)
    except Exception:
        import logging
        logging.getLogger("jnao").warning("growth: _overall_tier 失败，退回默认", exc_info=True)
    honor = get_tier_honor(overall_tier)
    # 回退：无训练进度时用打卡里程碑
    if honor == "新学员":
        for m in reversed(milestones):
            if m["achieved"]:
                honor = m["level"]
                break

    user = stats["user"]
    # 主导天赋：只用用户已确认写入 profile 的天赋，不用最新测评记录
    talent_primary = None
    if user and isinstance(user.profile_json, dict):
        pj = user.profile_json
        if pj.get("talent_code") or pj.get("talent_primary"):
            talent_primary = pj.get("talent_primary")
    if not talent_primary:
        eff = resolve_effective_talent(db, child_user_id)
        talent_primary = (eff or {}).get("talent_primary")

    # 🆕 积分：按已发生行为累计（打卡 10 分/次 + 提问 5 分/次 + 测评 20 分）
    points = (
        stats["checkins"] * 10
        + stats["qa_count"] * 5
        + (20 if stats.get("assessment") is not None else 0)
    )

    return {
        "nickname": user.nickname if user else "",
        "talent_primary": talent_primary,
        "overall_tier": overall_tier,        # 🆕 v2.0
        "honor_level": honor,
        "points": points,                    # 🆕 v2.1 积分
        "total_checkins": stats["checkins"],
        "checkin_streak": stats["streak"],
        "qa_questions": stats["qa_count"],
        "badges_earned": earned,
        "badges_total": len(badges),
        "trained_skills": sorted(stats["trained_skills"]),
        "mastery_skills_done": sorted(stats["trained_skills"] & set(MASTERY_SKILLS)),
        "mastery_skills_target": list(MASTERY_SKILLS),
        "member_since": user.created_at.date().isoformat() if user and user.created_at else None,
    }


# 🆕 v2.2 六级九段：轻量段位摘要，供全局角标 / 训练页状态卡使用
# 六级 = 前 3 级账户身份（会员/VIP会员/导师子女，与付费有关）+ 后 3 级训练称号（传承特使/劲脑学神/专利精英）
TIER_TITLES = [
    ("会员", "identity"),
    ("VIP会员", "identity"),
    ("导师子女", "identity"),
    ("传承特使", 1),
    ("劲脑学神", 5),
    ("专利精英", 8),
]


def get_tier_brief(db: Session, child_user_id: int) -> dict:
    """返回六级九段摘要，供全页面角标展示。

    - overall_tier: 九段（1-9，只按有打卡记录的技能取 tier 最小值，与打卡结算一致）
    - honor_level:  训练称号（三段映射）
    - title:        当前称号，优先账户身份（profile_json 里手动维护），否则用训练称号
    - next_title / need: 距下一称号还差几阶（null = 已最高）
    - advance_pass: 连续达标几次升 1 段（晋级规则，读配置）
    - skills:       5 个训练项目明细（段位 / 连续达标次数 / 达标标准文案 / 是否练过）
    """
    from app.services.child_training_state import (
        REQUIRED_SKILLS,
        _grade_band_from_grade,
        filter_active_skills,
        get_skills_with_records,
        get_training_progress,
        overall_tier as _overall_tier,
    )

    user = db.get(ChildUser, child_user_id)
    state = {}
    overall_tier = 1
    skills_with_records: set = set()
    try:
        if user:
            state = get_training_progress(user)
            skills_with_records = get_skills_with_records(db, child_user_id)
            overall_tier = _overall_tier(filter_active_skills(state, skills_with_records))
    except Exception:
        import logging
        logging.getLogger("jnao").warning("growth: get_tier_brief overall_tier 失败，退回默认", exc_info=True)

    honor = get_tier_honor(overall_tier)

    # 账户身份：profile_json 里手动维护的会员等级，优先展示
    identity = None
    if user and isinstance(user.profile_json, dict):
        identity = user.profile_json.get("member_level") or user.profile_json.get("identity")
    title = identity if identity else honor

    # 下一称号（只追训练称号这 3 级）
    next_title = None
    need = None
    for name, cond in TIER_TITLES:
        if isinstance(cond, int) and overall_tier < cond:
            next_title = name
            need = cond - overall_tier
            break

    # 晋级规则：连续达标几次升 1 段（读配置，默认 3）
    advance_pass = 3
    try:
        from config.loader import load_training_tier_thresholds
        advance_pass = int((load_training_tier_thresholds().get("advance_rule") or {}).get("consecutive_pass") or 3)
    except Exception:
        pass

    # 达标标准按学段取
    grade_band = None
    if user and isinstance(user.profile_json, dict):
        pj = user.profile_json
        grade = pj.get("grade") or (pj.get("learner") or {}).get("grade")
        if grade:
            grade_band = _grade_band_from_grade(grade)

    # 5 项目明细
    state_skills = state.get("skills") or {}
    skills = []
    for sk in REQUIRED_SKILLS:
        sd = state_skills.get(sk) or {}
        tier = int(sd.get("tier") or 1)
        skills.append({
            "name": sk,
            "tier": tier,
            "consecutive_pass": int(sd.get("consecutive_pass") or 0),
            "active": sk in skills_with_records,
            "rule_text": _skill_rule_text(sk, tier, grade_band),
        })

    return {
        "overall_tier": overall_tier,
        "tier_percent": round(overall_tier / 9 * 100),
        "honor_level": honor,
        "title": title,
        "next_title": next_title,
        "need": need,
        "advance_pass": advance_pass,
        "skills": skills,
    }


def _skill_rule_text(skill: str, tier: int, grade_band: str | None) -> str:
    """达标标准 → 人类可读文案（前端直接展示）"""
    from app.services.training_mastery import get_skill_threshold

    th = get_skill_threshold(skill, tier, grade_band)
    if not th:
        return "只练不考"
    rtype = th.get("type")
    if rtype == "wpm":
        words = int(th.get("words") or 0)
        minutes = max(int(th.get("minutes") or 1), 1)
        return f"每分钟≥{round(words / minutes)}字"
    if rtype == "recall":
        parts = []
        if th.get("words"):
            parts.append(f"≥{int(th['words'])}字")
        if th.get("accuracy_pct"):
            parts.append(f"准确率≥{int(th['accuracy_pct'])}%")
        return "、".join(parts)
    if rtype == "memory":
        s = f"≥{int(th.get('words_per_min') or 0)}字/分"
        if th.get("reverse_recite"):
            s += " 可倒背"
        return s
    if rtype == "speed_calc":
        return "完成速算题"
    if rtype == "program":
        return f"完成{th.get('name') or '训练项目'}"
    return "练熟即可"


def get_share(db: Session, child_user_id: int) -> dict:
    stats = _collect_stats(db, child_user_id)
    summary = get_summary(db, child_user_id, stats=stats)
    badges = [b for b in get_badges(db, child_user_id, stats=stats) if b["earned"]]
    badge_line = "、".join(b["name"] for b in badges[:5]) or "继续努力中"
    talent = summary["talent_primary"] or "天赋学员"
    lines = [
        f"🌟 {summary['nickname']} 在劲脑天赋成长平台坚持学习啦！",
        f"主导天赋：{talent}",
        f"荣誉级别：{summary['honor_level']}",
        f"累计打卡 {summary['total_checkins']} 次 · 连续 {summary['checkin_streak']} 天",
        f"学科提问 {summary['qa_questions']} 次",
        f"已获徽章：{badge_line}",
        "",
        "一起来打卡训练，遇见更好的自己 ✨",
        "#劲脑天赋 #成长里程碑",
    ]
    text = "\n".join(lines)
    return {
        "title": f"{summary['nickname']}的成长成就",
        "text": text,
        "highlights": [
            f"主导天赋：{talent}",
            f"荣誉级别：{summary['honor_level']}",
            f"累计打卡 {summary['total_checkins']} 次",
            f"已获得 {summary['badges_earned']} 枚徽章",
        ],
    }
