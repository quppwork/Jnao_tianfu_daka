"""续推规则：感知力不续推；主练打卡后辅练不续推；进阶后清空昨日续推"""

from app.db.models import TrainingItem
from app.services.training_carryover import (
    item_skips_checkin,
    should_carryover_item,
    yesterday_primary_checkin_complete,
)


def _item(skill: str, done: bool, title: str = "", ability: str = "audio") -> TrainingItem:
    import json

    item_type = "perception" if skill == "感知力" else "audio"
    return TrainingItem(
        plan_id=1,
        sort_order=1,
        ability_type=ability if skill == "感知力" else "audio",
        title=title or skill,
        instructions=json.dumps(
            {"block": "A" if skill == "超脑阅读" else "B", "item_type": item_type, "skill": skill},
            ensure_ascii=False,
        ),
        checkin_status="done" if done else "pending",
    )


class TestCarryoverRules:
    def test_perception_skips_checkin(self):
        it = _item("感知力", False, "学者多元感知", ability="perception")
        assert item_skips_checkin(it)

    def test_reading_incomplete_carries(self):
        items = [_item("超脑阅读", False)]
        it = items[0]
        assert should_carryover_item(
            it,
            yesterday_line_key="A",
            current_line_index=0,
            yesterday_items=items,
        )

    def test_perception_not_carried_when_reading_done(self):
        items = [
            _item("超脑阅读", True),
            _item("感知力", False, "多元感知", ability="perception"),
        ]
        perception = items[1]
        assert not should_carryover_item(
            perception,
            yesterday_line_key="A",
            current_line_index=0,
            yesterday_items=items,
        )

    def test_no_carryover_after_main_line_advanced(self):
        items = [_item("超脑阅读", False)]
        assert not should_carryover_item(
            items[0],
            yesterday_line_key="A",
            current_line_index=1,
            yesterday_items=items,
        )

    def test_yesterday_primary_complete(self):
        items = [_item("超脑阅读", True), _item("感知力", False, ability="perception")]
        assert yesterday_primary_checkin_complete(items, "A")
