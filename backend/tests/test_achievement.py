"""成就/荣誉系统测试"""

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    AchievementDefinition,
    AchievementShowcase,
    UserAchievement,
    UserTitle,
)
from app.services import achievement_service
from app.services.achievement_service import AchievementError


class TestAchievementDefinitions:
    """勋章定义初始化测试"""

    def test_init_achievements(self, db_session: Session):
        """测试初始化勋章定义"""
        count = achievement_service.init_achievement_definitions(db_session)
        assert count > 0

        # 验证幂等性
        count2 = achievement_service.init_achievement_definitions(db_session)
        assert count2 == 0

        # 验证数据
        defs = db_session.query(AchievementDefinition).all()
        assert len(defs) >= 10

        # 检查特定勋章
        streak_7 = db_session.query(AchievementDefinition).filter_by(code="streak_7").first()
        assert streak_7 is not None
        assert streak_7.name == "初窥门径"
        assert streak_7.title == "逐光者"
        assert streak_7.category == "streak"


class TestUserAchievements:
    """用户勋章状态测试"""

    def test_get_user_achievements_empty(self, db_session: Session, registered_user: dict):
        """测试获取用户勋章（未解锁任何）"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        items = achievement_service.get_user_achievements(db_session, user_id)
        assert len(items) > 0

        # 所有勋章应为 locked
        for item in items:
            assert item["status"] == "locked"
            assert item["progress_current"] >= 0

    def test_claim_achievement_not_ready(self, db_session: Session, registered_user: dict):
        """测试领取未满足的勋章"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        # 找一个需要100次打卡的勋章
        milestone = db_session.query(AchievementDefinition).filter_by(code="milestone_100").first()
        assert milestone is not None

        with pytest.raises(AchievementError) as exc:
            achievement_service.claim_achievement(db_session, user_id, milestone.id)
        assert "尚未满足解锁条件" in str(exc.value)

    def test_claim_achievement_success(self, db_session: Session, registered_user: dict):
        """测试成功领取勋章"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        # 模拟完成测评（满足 streak_1 条件）
        from app.db.models import TalentAssessment
        assessment = TalentAssessment(
            child_user_id=user_id,
            report_json={"talent": "学者"},
        )
        db_session.add(assessment)
        db_session.commit()

        # 触发检查
        newly_ready = achievement_service.check_and_update_achievements(db_session, user_id)
        assert len(newly_ready) > 0

        # 领取勋章
        streak_1 = db_session.query(AchievementDefinition).filter_by(code="streak_1").first()
        result = achievement_service.claim_achievement(db_session, user_id, streak_1.id)

        assert result["code"] == "streak_1"
        assert result["name"] == "初露锋芒"
        assert result["title"] == "新芽"

        # 再次领取应失败
        with pytest.raises(AchievementError) as exc:
            achievement_service.claim_achievement(db_session, user_id, streak_1.id)
        assert "已领取过" in str(exc.value)


class TestUserTitle:
    """用户称号测试"""

    def test_set_title_not_unlocked(self, db_session: Session, registered_user: dict):
        """测试设置未解锁的称号"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        with pytest.raises(AchievementError) as exc:
            achievement_service.set_user_title(db_session, user_id, "新芽")
        assert "尚未解锁" in str(exc.value)

    def test_set_title_success(self, db_session: Session, registered_user: dict):
        """测试设置已解锁的称号"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        # 完成测评并领取勋章
        from app.db.models import TalentAssessment
        assessment = TalentAssessment(child_user_id=user_id, report_json={"talent": "学者"})
        db_session.add(assessment)
        db_session.commit()

        achievement_service.check_and_update_achievements(db_session, user_id)
        streak_1 = db_session.query(AchievementDefinition).filter_by(code="streak_1").first()
        achievement_service.claim_achievement(db_session, user_id, streak_1.id)

        # 设置称号
        result = achievement_service.set_user_title(db_session, user_id, "新芽")
        assert result["title"] == "新芽"
        assert result["name"] == "初露锋芒"

        # 获取称号
        title = achievement_service.get_user_title(db_session, user_id)
        assert title is not None
        assert title["title"] == "新芽"


class TestShowcase:
    """荣誉展柜测试"""

    def test_get_showcase_empty(self, db_session: Session, registered_user: dict):
        """测试获取空展柜"""
        user_id = registered_user["child_user_id"]
        slots = achievement_service.get_showcase(db_session, user_id)

        assert len(slots) == 3
        for slot in slots:
            assert slot["empty"] is True

    def test_set_showcase_not_unlocked(self, db_session: Session, registered_user: dict):
        """测试设置未解锁的勋章到展柜"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        milestone = db_session.query(AchievementDefinition).filter_by(code="milestone_100").first()

        with pytest.raises(AchievementError) as exc:
            achievement_service.set_showcase_slot(db_session, user_id, 0, milestone.id)
        assert "已解锁" in str(exc.value)

    def test_set_showcase_success(self, db_session: Session, registered_user: dict):
        """测试成功设置展柜"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        # 完成测评并领取勋章
        from app.db.models import TalentAssessment
        assessment = TalentAssessment(child_user_id=user_id, report_json={"talent": "学者"})
        db_session.add(assessment)
        db_session.commit()

        achievement_service.check_and_update_achievements(db_session, user_id)
        streak_1 = db_session.query(AchievementDefinition).filter_by(code="streak_1").first()
        achievement_service.claim_achievement(db_session, user_id, streak_1.id)

        # 设置到展柜
        result = achievement_service.set_showcase_slot(db_session, user_id, 0, streak_1.id)
        assert result["slot"] == 0
        assert result["name"] == "初露锋芒"

        # 获取展柜
        slots = achievement_service.get_showcase(db_session, user_id)
        assert "empty" not in slots[0]  # 有数据的槽位没有 empty 键
        assert slots[0]["name"] == "初露锋芒"
        assert slots[1]["empty"] is True

        # 清空槽位
        result = achievement_service.set_showcase_slot(db_session, user_id, 0, None)
        assert result["empty"] is True

    def test_set_showcase_invalid_slot(self, db_session: Session, registered_user: dict):
        """测试设置无效槽位"""
        user_id = registered_user["child_user_id"]

        with pytest.raises(AchievementError) as exc:
            achievement_service.set_showcase_slot(db_session, user_id, 5, None)
        assert "无效" in str(exc.value)


class TestStats:
    """成就统计测试"""

    def test_get_stats(self, db_session: Session, registered_user: dict):
        """测试获取统计"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        stats = achievement_service.get_achievement_stats(db_session, user_id)
        assert "total" in stats
        assert "claimed" in stats
        assert "ready" in stats
        assert "locked" in stats
        assert stats["total"] == stats["claimed"] + stats["ready"] + stats["locked"]


    def test_skill_tier_reads_training_progress(self, db_session: Session, registered_user: dict):
        """技能勋章进度从 training_progress.skills 读取，达到三阶即可领取"""
        from app.db.models import ChildUser

        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]
        child = db_session.get(ChildUser, user_id)
        child.profile_json = {
            "training_progress": {
                "skills": {
                    "超脑阅读": {"tier": 3},
                    "影像追忆": {"tier": 1},
                    "扫描速记": {"tier": 2},
                }
            }
        }
        db_session.commit()

        items = {i["code"]: i for i in achievement_service.get_user_achievements(db_session, user_id)}
        reading = items["skill_speed_reading_t3"]
        assert reading["progress_current"] == 3
        assert reading["status"] == "ready"
        assert "三阶" in reading["progress_text"]
        assert items["skill_memory_t3"]["status"] == "locked"
        assert items["skill_scan_t3"]["progress_current"] == 2


# ─── API 测试 ────────────────────────────────────────


class TestAchievementAPI:
    """成就 API 测试"""

    def test_get_list(self, client, db_session, registered_user: dict):
        """测试获取勋章列表 API"""
        # 先初始化勋章定义
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        res = client.get("/api/achievement/list", params={"user_id": user_id})
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "stats" in data
        assert len(data["items"]) > 0

    def test_get_stats_api(self, client, db_session, registered_user: dict):
        """测试获取统计 API"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        res = client.get("/api/achievement/stats", params={"user_id": user_id})
        assert res.status_code == 200
        data = res.json()
        assert "total" in data

    def test_claim_api(self, client, db_session, registered_user: dict):
        """测试领取勋章 API"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        # 先检查（会创建记录）
        client.post("/api/achievement/check", params={"user_id": user_id})

        # 尝试领取（应该失败，因为未满足条件）
        res = client.post("/api/achievement/claim", params={"user_id": user_id}, json={"achievement_id": 999})
        assert res.status_code in [400, 404]

    def test_get_showcase_api(self, client, db_session, registered_user: dict):
        """测试获取展柜 API"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        res = client.get("/api/achievement/showcase", params={"user_id": user_id})
        assert res.status_code == 200
        data = res.json()
        assert "slots" in data
        assert len(data["slots"]) == 3

    def test_get_title_api(self, client, db_session, registered_user: dict):
        """测试获取称号 API"""
        achievement_service.init_achievement_definitions(db_session)
        user_id = registered_user["child_user_id"]

        res = client.get("/api/achievement/title", params={"user_id": user_id})
        assert res.status_code == 200
        data = res.json()
        assert "title" in data  # 可能是 null
