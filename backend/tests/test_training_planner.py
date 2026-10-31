"""今日修炼 planner：默认路径必须改变清单（非旁路脚手架）"""

from types import SimpleNamespace

from app.services.training.cohort import build_cohort_context, resolve_cohort, resolve_plan_mode
from app.services.training.planner import plan_today_slots
from app.services.training_formula_engine import expand_formula
from config.loader import load_training_recipes


def _child(profile: dict | None = None, *, training_days: int | None = None):
    pj = dict(profile or {})
    if training_days is not None:
        tr = dict(pj.get("training") or {})
        # 写入 progress 供 get_training_progress 读取
        pj["training_progress"] = {
            "skills": {},
            "training_days": training_days,
            "training_day_anchor": None,
        }
        pj["training"] = tr
    return SimpleNamespace(id=1, profile_json=pj, training_level=None)


class TestDefaultPathActuallyChanges:
    """验收：零训练日默认体验固定表，不再等于旧权重。"""

    def test_zero_days_is_experience(self):
        assert resolve_cohort(_child()) == "experience"

    def test_zero_days_40min_not_equal_weight(self):
        child = _child()
        got = plan_today_slots(child, 40, overall_tier=1, grade_band="primary_low")
        weight = expand_formula(40, overall_tier=1, grade_band="primary_low")
        assert got["schedule_engine"] == "fixed"
        assert got["slots"] == ["超脑阅读"]
        assert got["slots"] != weight["slots"]  # 权重 40min=[超脑,影像]

    def test_zero_days_60min_experience(self):
        got = plan_today_slots(_child(), 60, overall_tier=1, grade_band="primary_low")
        assert got["slots"] == ["超脑阅读", "影像追忆"]
        assert got["recipe_id"] == "experience_60"

    def test_zero_days_120_uses_new_student_fixed(self):
        got = plan_today_slots(_child(), 120, overall_tier=1, grade_band="primary_low")
        assert got["schedule_engine"] == "fixed"
        # 开发设定 90–180：超脑+影像 轮换 + 多元感知 + 扫描
        assert got["slots"] == [
            "超脑阅读", "影像追忆", "超脑阅读", "影像追忆", "多元感知", "扫描速记"
        ]
        weight = expand_formula(120, overall_tier=1, grade_band="primary_low")
        assert got["slots"] != weight["slots"]

    def test_day3_new_student_fixed(self):
        child = _child(training_days=3)
        assert resolve_cohort(child) == "new_student"
        got = plan_today_slots(child, 90, overall_tier=1, grade_band="primary_low")
        assert got["schedule_engine"] == "fixed"
        assert got["slots"] == ["超脑阅读", "影像追忆", "扫描速记"]

    def test_old_student_still_weight(self):
        child = _child({"training": {"cohort": "regular"}}, training_days=20)
        # 显式 regular
        child = _child({"training": {"cohort": "regular"}})
        got = plan_today_slots(child, 90, overall_tier=1, grade_band="primary_low")
        weight = expand_formula(90, overall_tier=1, grade_band="primary_low")
        assert got["slots"] == weight["slots"]
        assert got["schedule_engine"] == "weight"


class TestExplicitRecipes:
    def test_experience_advanced(self):
        child = _child({"training": {"cohort": "experience", "recipe_variant": "advanced"}})
        r = plan_today_slots(child, 60, overall_tier=1, grade_band="primary_low")
        assert r["slots"] == ["多元感知", "影像追忆"]

    def test_rocket(self):
        child = _child({"training": {"cohort": "rocket"}})
        r = plan_today_slots(child, 300, overall_tier=2, grade_band="junior")
        assert r["slots"] == ["超脑阅读", "影像追忆", "极速学习"]

    def test_blackhorse_has_scan(self):
        child = _child({"training": {"cohort": "blackhorse"}})
        r = plan_today_slots(child, 300, overall_tier=2, grade_band="junior")
        assert "扫描速记" in r["slots"]

    def test_academic_appends_subjects(self):
        child = _child({"training": {"plan_mode": "academic", "cohort": "regular"}})
        got = plan_today_slots(child, 90, overall_tier=1, grade_band="primary_low")
        assert "学科方案" in got["slots"]
        assert "三错一讲" in got["slots"]

    def test_recipes_v2(self):
        assert load_training_recipes().get("version") == 2
