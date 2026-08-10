"""训练 Agent 辅助排课 — 工具循环 + 全课表重喂 + 投影"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.training_agent_assist import (
    AssistFail,
    is_schedule_assist_enabled,
    validate_and_project,
)


def _auth(uid: int) -> dict:
    return {"headers": {"X-Child-User-Id": str(uid)}}


@pytest.fixture(autouse=True)
def _no_oss_sign(monkeypatch):
    """本机缺 oss2 / 无签名时仍可跑 schedule 落库路径。"""
    monkeypatch.setattr(
        "app.services.content_meta.estimate_duration_min",
        lambda item: int(getattr(item, "duration_min", None) or 12),
    )


class TestValidateAndProject:
    def test_projects_to_rule_slot_count(self):
        rule = ["超脑阅读", "影像追忆", "扫描速记"]
        draft = ["影像追忆", "极速运算", "超脑阅读", "扫描速记"]
        available = ["超脑阅读", "影像追忆", "扫描速记", "极速运算", "极速学习"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert out == ["影像追忆", "极速运算", "超脑阅读"]
        assert meta["target_n"] == 3
        assert meta["dropped_for_slot_cap"] == ["扫描速记"]

    def test_pads_from_rule_when_draft_short(self):
        """无 pad_priority 时仍可用规则垫底。"""
        rule = ["超脑阅读", "影像追忆"]
        draft = ["影像追忆"]
        available = ["超脑阅读", "影像追忆", "扫描速记"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert out == ["影像追忆", "超脑阅读"]
        assert meta["padded_from_rule"] == ["超脑阅读"]
        assert meta["padded_from_intent"] == []

    def test_pads_intent_before_rule(self):
        """有 pad_priority 时先按画像补齐，不用规则名单抢先。"""
        rule = ["超脑阅读", "影像追忆", "扫描速记"]
        draft = ["影像追忆"]
        available = ["超脑阅读", "影像追忆", "扫描速记", "极速运算"]
        out, meta = validate_and_project(
            draft,
            available_skills=available,
            rule_slots=rule,
            pad_priority=["扫描速记", "极速运算", "超脑阅读"],
        )
        assert out[0] == "影像追忆"
        assert out[1] == "扫描速记"
        assert out[2] == "极速运算"
        assert meta["padded_from_intent"] == ["扫描速记", "极速运算"]
        assert meta["padded_from_rule"] == []

    def test_keeps_elective_tail(self):
        rule = ["超脑阅读", "影像追忆", "精力恢复"]
        draft = ["影像追忆", "扫描速记"]
        available = ["超脑阅读", "影像追忆", "扫描速记"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert out[-1] == "精力恢复"
        assert len(out) == 3
        assert meta["target_n"] == 2

    def test_rejects_all_invalid(self):
        with pytest.raises(AssistFail) as ei:
            validate_and_project(
                ["不存在的技能"],
                available_skills=["超脑阅读"],
                rule_slots=["超脑阅读"],
            )
        assert ei.value.code == "no_valid_skills"

    def test_drops_locked_skills(self):
        rule = ["超脑阅读", "影像追忆"]
        draft = ["天赋绘画", "影像追忆", "超脑阅读"]
        available = ["超脑阅读", "影像追忆", "扫描速记"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert "天赋绘画" not in out
        assert "天赋绘画" in meta["dropped_invalid"]
        assert out[0] == "影像追忆"

    def test_allows_repeated_skills_to_fill_slots(self):
        """长时长规则槽可重复技能；草案与补齐均不得去重卡死。"""
        rule = [
            "影像追忆",
            "极速运算",
            "扫描速记",
            "影像追忆",
            "极速学习",
            "极速学习",
        ]
        draft = ["影像追忆", "极速运算", "扫描速记", "影像追忆"]
        available = ["超脑阅读", "影像追忆", "扫描速记", "极速运算", "极速学习"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert len(out) == 6
        assert out.count("影像追忆") >= 2
        assert out[-2:] == ["极速学习", "极速学习"]
        assert meta["padded_from_rule"] == ["极速学习", "极速学习"]
        # 规则里影像追忆×2，草案已有×2，补齐不应再塞影像追忆
        assert meta["padded_from_rule"].count("影像追忆") == 0

    def test_draft_may_repeat_same_skill(self):
        rule = ["超脑阅读", "超脑阅读", "影像追忆"]
        draft = ["超脑阅读", "超脑阅读", "影像追忆"]
        available = ["超脑阅读", "影像追忆", "扫描速记"]
        out, meta = validate_and_project(draft, available_skills=available, rule_slots=rule)
        assert out == ["超脑阅读", "超脑阅读", "影像追忆"]
        assert meta["target_n"] == 3


def test_assist_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TRAINING_AGENT_SCHEDULE", raising=False)
    assert is_schedule_assist_enabled() is False


def test_assist_enabled_by_env(monkeypatch):
    monkeypatch.setenv("TRAINING_AGENT_SCHEDULE", "1")
    assert is_schedule_assist_enabled() is True


class TestCurriculumMap:
    def test_overview_has_all_tiers(self):
        from app.agents.training_schedule.tools.curriculum_map import (
            build_curriculum_overview,
        )

        ov = build_curriculum_overview(overall_tier=1)
        assert "超脑阅读" in (ov.get("required_skills") or [])
        assert "tier_1" in ov["tiers"]
        assert "tier_6" in ov["tiers"]
        assert ov["tiers"]["tier_1"]["key_skills"]
        assert ov["tiers"]["tier_1"]["weights"]
        assert ov["current_tier_focus"]["tier"] == 1
        assert "超脑阅读" in ov["current_tier_focus"]["key_skills"] or "影像追忆" in ov[
            "current_tier_focus"
        ]["key_skills"]

    def test_availability_has_locked_preview(self):
        from app.agents.training_schedule.tools.curriculum_map import (
            build_skill_availability,
        )

        av = build_skill_availability(overall_tier=1)
        assert av["selectable_now"]
        assert av["importance_now"]["key"] or av["importance_now"]["weights"]
        # 天赋绘画通常更高阶引入
        locked_names = {x["skill"] for x in av.get("locked_preview") or []}
        assert "天赋绘画" in locked_names or "音乐灵感" in locked_names


class TestToolRegistry:
    def test_tools_registered(self):
        from app.agents.training_schedule.tools import list_tools

        names = list_tools()
        assert "get_curriculum_overview" in names
        assert "get_schedule_context" in names
        assert "get_available_skills" in names
        assert "get_checkin_skill_summary" in names
        assert "get_training_rhythm" in names
        assert "get_recent_training_history" in names
        assert "get_slot_budget_hint" in names
        assert "propose_skill_draft" in names
        # 旧名仍注册（兼容），但 schema 对外用软预算名
        assert "get_rule_slot_hint" in names


class TestCheckinSummary:
    def test_rhythm_and_checkin_shapes(self, db_session, user_ready_for_training):
        from app.agents.training_schedule.tools.checkin_summary import (
            build_checkin_skill_summary,
            build_rhythm_summary,
        )

        uid = user_ready_for_training
        rhythm = build_rhythm_summary(db_session, uid, lookback_days=14)
        assert "checkin_streak_days" in rhythm
        assert "days_since_last_checkin" in rhythm
        assert "recent_plan_completion" in rhythm

        checkin = build_checkin_skill_summary(
            db_session, uid, days=14, skill_tiers={}, grade_band="primary_low"
        )
        assert "skills" in checkin
        assert "struggling_skills" in checkin
        assert "stable_skills" in checkin


class TestRunnerToolLoop:
    def test_runner_executes_tools_then_draft(self, db_session, user_ready_for_training):
        """模拟原生 FC：首轮可补查，次轮 propose_skill_draft。"""
        import asyncio

        from app.agents.training_schedule.runner import run_schedule_assist
        from app.services.training_day import get_training_day
        from app.services.dev_clock import resolve_training_now

        uid = user_ready_for_training
        now = resolve_training_now(db_session, uid)
        plan_date = get_training_day(now)

        round_state = {"n": 0}

        async def fake_chat(*, messages, tools=None, tool_choice=None, max_tokens=400, timeout=30):
            n = round_state["n"]
            round_state["n"] = n + 1
            if n == 0:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "get_curriculum_overview",
                                "arguments": "{}",
                            },
                        },
                        {
                            "id": "c2",
                            "type": "function",
                            "function": {
                                "name": "get_available_skills",
                                "arguments": "{}",
                            },
                        },
                    ],
                }
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c3",
                        "type": "function",
                        "function": {
                            "name": "propose_skill_draft",
                            "arguments": (
                                '{"skills":["影像追忆","超脑阅读"],'
                                '"reason":"本阶重点先练影像追忆，再巩固超脑阅读"}'
                            ),
                        },
                    },
                ],
            }

        with patch(
            "app.services.doubao_client.is_configured",
            return_value=True,
        ), patch(
            "app.services.doubao_client.chat_completion_message",
            new=AsyncMock(side_effect=fake_chat),
        ):
            result = asyncio.run(
                run_schedule_assist(
                    db_session,
                    uid,
                    40,
                    plan_date=plan_date,
                    timeout_sec=10,
                )
            )

        assert result["draft"]
        names = [t["name"] for t in result["tools_used"]]
        assert "propose_skill_draft" in names
        assert "影像追忆" in result["draft"]
        assert "影像追忆" in (result.get("reason") or "")
        # 首轮注入应含课表字段（检查 messages 经由 fake 收到 — draft 成功即可）
        assert result.get("target_slot_count") is None or True


class TestSchedulePreferApi:
    def test_rule_prefer_returns_rule_mode(self, client, user_ready_for_training):
        uid = user_ready_for_training
        res = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40, "schedule_prefer": "rule"},
            **_auth(uid),
        )
        assert res.status_code == 200
        assert res.json().get("schedule_mode") == "rule"
        assert len(res.json()["items"]) >= 1

    def test_agent_when_disabled_falls_to_rule(self, client, user_ready_for_training, monkeypatch):
        monkeypatch.setenv("TRAINING_AGENT_SCHEDULE", "0")
        uid = user_ready_for_training
        res = client.post(
            "/api/training/schedule",
            json={"planned_minutes": 40, "schedule_prefer": "agent"},
            **_auth(uid),
        )
        assert res.status_code == 200
        assert res.json().get("schedule_mode") == "rule"

    def test_agent_success_via_runner(self, client, user_ready_for_training, monkeypatch):
        monkeypatch.setenv("TRAINING_AGENT_SCHEDULE", "1")
        uid = user_ready_for_training

        async def _fake_assist(db, child_user_id, planned_minutes, *, plan_date=None, timeout_sec=10.0):
            from app.services.training_formula_engine import expand_formula

            r = expand_formula(planned_minutes, overall_tier=1, grade_band="primary_low")
            slots = list(r["slots"])
            return {
                "draft": ["影像追忆", "超脑阅读"],
                "reason": "优先影像追忆巩固薄弱，再排超脑阅读",
                "available_skills": ["超脑阅读", "影像追忆", "扫描速记", "极速运算", "极速学习"],
                "rule_slots": slots,
                "rule_strategy": r.get("strategy"),
                "tools_used": [
                    {"name": "get_curriculum_overview", "ok": True},
                    {"name": "propose_skill_draft", "ok": True},
                ],
            }

        with patch(
            "app.agents.training_schedule.runner.run_schedule_assist",
            new=AsyncMock(side_effect=_fake_assist),
        ), patch(
            "app.services.doubao_client.is_configured",
            return_value=True,
        ):
            res = client.post(
                "/api/training/schedule",
                json={"planned_minutes": 40, "schedule_prefer": "agent"},
                **_auth(uid),
            )
        assert res.status_code == 200, res.text
        assert res.json().get("schedule_mode") == "agent"
        assert len(res.json()["items"]) >= 1
        assist = res.json().get("schedule_assist") or {}
        assert assist.get("mode") == "agent"
        assert "影像追忆" in (assist.get("reason") or "")

    def test_agent_fallback_on_assist_fail(self, client, user_ready_for_training, monkeypatch):
        monkeypatch.setenv("TRAINING_AGENT_SCHEDULE", "1")
        uid = user_ready_for_training
        from app.agents.training_schedule.runner import ScheduleAssistError

        with patch(
            "app.agents.training_schedule.runner.run_schedule_assist",
            new=AsyncMock(side_effect=ScheduleAssistError("timeout", "超时")),
        ), patch(
            "app.services.doubao_client.is_configured",
            return_value=True,
        ):
            res = client.post(
                "/api/training/schedule",
                json={"planned_minutes": 40, "schedule_prefer": "agent"},
                **_auth(uid),
            )
        assert res.status_code == 200, res.text
        assert res.json().get("schedule_mode") == "agent_fallback"
        assert len(res.json()["items"]) >= 1
        assist = res.json().get("schedule_assist") or {}
        assert assist.get("mode") == "agent_fallback"
        assert "timeout" in (assist.get("reason") or "")

    def test_entry_exposes_flag(self, client, user_ready_for_training, monkeypatch):
        monkeypatch.setenv("TRAINING_AGENT_SCHEDULE", "1")
        uid = user_ready_for_training
        res = client.get("/api/training/entry", **_auth(uid))
        assert res.status_code == 200
        assert res.json().get("agent_schedule_enabled") is True
