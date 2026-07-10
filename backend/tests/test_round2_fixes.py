"""第二轮逻辑漏洞修复回归测试"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingItem, TrainingPlan, TrainingRecord
from app.services import auth_service
from app.services.training_formula_engine import duration_slot, max_formula_item_count
from app.services.training_schedule_service import _plan_structure_invalid
from app.services.training_service import append_elective_item, customize_plan_items, remove_plan_item


class TestDurationSlot:
    def test_duration_slot_defined(self):
        cfg = duration_slot(60)
        assert cfg["items"] >= 1
        assert cfg["minutes"] == 60

    def test_max_formula_item_count_grows_with_minutes(self):
        assert max_formula_item_count(20) <= max_formula_item_count(120)

    def test_plan_structure_invalid_v2_multi_item(self):
        plan = TrainingPlan(
            child_user_id=1,
            plan_date=date(2026, 7, 6),
            level="视觉",
            report_text="",
            status="pending",
            planned_minutes=60,
        )
        plan.items = [
            TrainingItem(
                plan_id=0,
                sort_order=1,
                ability_type="audio",
                title="超脑阅读",
                duration_min=10,
                instructions=json.dumps({"skill": "超脑阅读", "item_type": "required"}),
                checkin_status="pending",
            ),
            TrainingItem(
                plan_id=0,
                sort_order=2,
                ability_type="audio",
                title="影像追忆",
                duration_min=10,
                instructions=json.dumps({"skill": "影像追忆", "item_type": "required"}),
                checkin_status="pending",
            ),
        ]
        assert _plan_structure_invalid(plan, 60) is False


class TestElectiveDedup:
    def test_placeholder_elective_not_duplicated(self, db_session: Session):
        user = auth_service.register_child(
            db_session,
            parent_phone="13900008801",
            nickname="选修童",
            login_name="elec_kid",
            password="123456",
        )
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=date(2026, 7, 6),
            level="视觉",
            report_text="",
            status="pending",
            planned_minutes=60,
        )
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingItem(
                plan_id=plan.id,
                sort_order=1,
                ability_type="elective",
                title="多元感知（待同步）",
                duration_min=0,
                instructions=json.dumps({"skill": "多元感知", "item_type": "elective"}),
                checkin_status="pending",
            )
        )
        db_session.commit()
        db_session.refresh(plan)

        append_elective_item(db_session, user.id, plan.id, "多元感知")
        db_session.refresh(plan)
        skills = [
            json.loads(i.instructions).get("skill")
            for i in plan.items
            if i.instructions and i.instructions.startswith("{")
        ]
        assert skills.count("多元感知") == 1


class TestRemovePlanItem:
    def test_remove_clears_record_item_id(self, db_session: Session):
        user = auth_service.register_child(
            db_session,
            parent_phone="13900008802",
            nickname="删项童",
            login_name="rm_kid",
            password="123456",
        )
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=date(2026, 7, 6),
            level="视觉",
            report_text="",
            status="pending",
        )
        db_session.add(plan)
        db_session.flush()
        item = TrainingItem(
            plan_id=plan.id,
            sort_order=1,
            ability_type="elective",
            title="精力恢复",
            duration_min=0,
            instructions=json.dumps({"skill": "精力恢复", "item_type": "elective", "blocks_next": False}),
            checkin_status="pending",
        )
        db_session.add(item)
        db_session.flush()
        rec = TrainingRecord(
            child_user_id=user.id,
            plan_id=plan.id,
            item_id=item.id,
            train_date=plan.plan_date,
        )
        db_session.add(rec)
        db_session.commit()
        rec_id = rec.id

        remove_plan_item(db_session, user.id, item.id)
        db_session.refresh(rec)
        assert rec.item_id is None
        assert db_session.get(TrainingRecord, rec_id) is not None


class TestCustomizePlan:
    def test_empty_mutable_rejected(self, db_session: Session):
        user = auth_service.register_child(
            db_session,
            parent_phone="13900008803",
            nickname="编辑童",
            login_name="cust_kid",
            password="123456",
        )
        plan = TrainingPlan(
            child_user_id=user.id,
            plan_date=date(2026, 7, 6),
            level="视觉",
            report_text="",
            status="pending",
            planned_minutes=60,
        )
        db_session.add(plan)
        db_session.flush()
        db_session.add(
            TrainingItem(
                plan_id=plan.id,
                sort_order=1,
                ability_type="audio",
                title="超脑阅读",
                duration_min=10,
                instructions=json.dumps({"skill": "超脑阅读", "item_type": "required"}),
                checkin_status="done",
            )
        )
        db_session.commit()
        db_session.refresh(plan)

        from app.services.training_service import TrainingError

        with pytest.raises(TrainingError, match="没有可编辑"):
            customize_plan_items(db_session, user.id, plan.id, [])


class TestUnbindChild:
    def _admin_auth(self, client: TestClient) -> dict:
        data = client.post(
            "/api/admin/login",
            json={"login_name": "pyx", "password": "123456"},
        ).json()
        return {
            "params": {"user_id": data["child_user_id"]},
            "headers": {
                "X-Child-User-Id": str(data["child_user_id"]),
                "X-Session-Token": data["session_token"],
            },
        }

    def test_unbind_parent_id_rejected(self, client: TestClient, db_session: Session):
        from tests.test_parent_auth import STRONG_PWD, _register_parent

        auth = self._admin_auth(client)
        parent = _register_parent(client, "13900008804", password=STRONG_PWD)
        res = client.delete(f"/api/admin/children/{parent['child_user_id']}/bind", **auth)
        assert res.status_code == 404

    def test_unbind_clears_parent_fields(self, client: TestClient, db_session: Session):
        from tests.test_parent_auth import STRONG_PWD, _parent_auth, _register_parent

        auth = self._admin_auth(client)
        parent = _register_parent(client, "13900008805", password=STRONG_PWD)
        pauth = _parent_auth(parent)
        child = client.post(
            "/api/parent/children",
            json={"login_name": "clr_kid", "nickname": "清字段童", "password": "XiaoMing1"},
            **pauth,
        ).json()
        cid = child["id"]
        before = db_session.get(ChildUser, cid)
        assert before.parent_phone
        assert before.profile_json.get("parentName")

        res = client.delete(f"/api/admin/children/{cid}/bind", **auth)
        assert res.status_code == 200

        after = db_session.get(ChildUser, cid)
        assert after.parent_phone == ""
        assert "parentName" not in (after.profile_json or {})
