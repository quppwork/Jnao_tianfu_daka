# -*- coding: utf-8 -*-
"""Full workflow test suite for registration → onboarding → training → conflict → lock"""
import sys, json, os
sys.path.insert(0, '.')
os.environ['JNAO_ENV'] = 'development'
os.environ['JNAO_DEV_MODE'] = '1'

TEST_DB = 'data/test_workflow.db'
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'

from dotenv import load_dotenv
load_dotenv('.env', override=True)
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'

from app.db.session import get_session_factory, init_db
from app.db.models import ChildUser, TrainingRecord
from app.services.assessment_service import (
    save_assessment, sync_child_user_talent, get_latest_assessment,
    get_self_reported_talent_code, has_training_records, has_valid_talent,
    effective_talent_code, get_self_reported_talent_name, resolve_talent_conflict,
    TALENT_LOCK_MSG,
)
from app.services.training_service import get_training_entry, _resolve_effective_talent
from app.core.talent_mapping import resolve_talent_code

init_db()
db = get_session_factory()()

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  -- {detail}")

# ═══════════════════════════════════════════
print("=" * 60)
print("TEST 1: 自选天赋 → 训练放行")
print("=" * 60)

user = ChildUser(parent_phone="13800001111", nickname="test1")
db.add(user); db.commit(); db.refresh(user)
uid = user.id

# Simulate onboarding save
user.profile_json = {
    "onboarding": {
        "student_type": "new",
        "completed_at": "2026-06-28T10:00:00.000Z",
        "self_reported_talent": "学者",
        "self_reported_talent_code": 1,
        "talent_unknown": False,
    }
}
db.commit()

check("1a. 自选天赋可读", get_self_reported_talent_code(db, uid) == 1)
sync_child_user_talent(db, uid)
db.refresh(user)
check("1b. 天赋提升到top-level", user.training_level == "学者")

entry = get_training_entry(db, uid)
check("1c. 训练放行", entry["has_assessment"] and not entry["needs_assessment"])

# ═══════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 2: 自选学者 → JNAO测出行者 → 冲突")
print("=" * 60)

row = save_assessment(db, child_user_id=uid, jnao_record_id="t1",
    answer_bitstring="0"*35, test_type=1,
    report={"talent": "行者", "create_time": "2026-06-28 11:00"})
conflict = getattr(row, "_talent_conflict", False)
check("2a. 自选vs测评冲突触发", conflict)

db.refresh(user)
p = dict(user.profile_json or {})
check("2b. pending暂存", p.get("pending_talent", {}).get("talent_code") == 3)
check("2c. 旧天赋保留", p.get("talent_code") == 1)

r = resolve_talent_conflict(db, uid, action="use_new")
check("2d. 采用新天赋", r["talent_primary"] == "行者")
db.refresh(user)
p2 = dict(user.profile_json or {})
check("2e. 天赋已更新", p2.get("talent_code") == 3)

# ═══════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 3: 有训练记录 → 锁定")
print("=" * 60)

p3 = dict(user.profile_json or {})
p3["talent_code"] = 1; p3["talent_primary"] = "学者"; p3["talent_source"] = "onboarding"
user.profile_json = p3; user.training_level = "学者"; db.commit()

check("3a. 无训练记录", not has_training_records(db, uid))
db.add(TrainingRecord(child_user_id=uid, plan_id=1, item_id=1,
    ability_type="影像追忆", content="test"))
db.commit()
check("3b. 有训练记录", has_training_records(db, uid))

row2 = save_assessment(db, child_user_id=uid, jnao_record_id="t2",
    answer_bitstring="1"*35, test_type=1,
    report={"talent": "赢者", "create_time": "2026-06-28 12:00"})
check("3c. 锁定触发", getattr(row2, "_talent_locked", False))
db.refresh(user)
p3d = dict(user.profile_json or {})
check("3d. 锁定后天赋不变", p3d.get("talent_code") == 1)

# ═══════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 4: 迷者处理")
print("=" * 60)

check("4a. 迷者不映射", resolve_talent_code("迷者") is None)

user2 = ChildUser(parent_phone="13800002222", nickname="mizhe_user")
db.add(user2); db.commit(); db.refresh(user2)

row_m = save_assessment(db, child_user_id=user2.id, jnao_record_id="m1",
    answer_bitstring="0"*35, test_type=1,
    report={"talent": "迷者", "create_time": "2026-06-28 13:00"})
check("4b. 迷者talent_code=None", row_m.talent_code is None)
check("4c. 迷者has_valid=False", not has_valid_talent(row_m))
check("4d. 迷者effective=None", effective_talent_code(row_m) is None)

entry_m = get_training_entry(db, user2.id)
check("4e. 迷者训练拦截", entry_m["needs_assessment"])

# ═══════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 5: 边界情况")
print("=" * 60)

user3 = ChildUser(parent_phone="13800003333", nickname="unknown_user")
db.add(user3); db.commit(); db.refresh(user3)
user3.profile_json = {"onboarding": {
    "student_type": "new", "self_reported_talent": None,
    "self_reported_talent_code": None, "talent_unknown": True}}
db.commit()
check("5a. '不知道'不返回天赋", get_self_reported_talent_code(db, user3.id) is None)
check("5b. '不知道'训练拦截", get_training_entry(db, user3.id)["needs_assessment"])

user4 = ChildUser(parent_phone="13800004444", nickname="returning_user")
db.add(user4); db.commit(); db.refresh(user4)
user4.profile_json = {"onboarding": {"student_type": "returning"}}
db.commit()
sync_child_user_talent(db, user4.id)
db.refresh(user4)
p5c = dict(user4.profile_json or {})
check("5c. 老学员无天赋", p5c.get("talent_code") is None)

# JNAO retest (学者→行者) auto-updates (no conflict for JNAO→JNAO)
user5 = ChildUser(parent_phone="13800005555", nickname="retest_user")
db.add(user5); db.commit(); db.refresh(user5)
row_a = save_assessment(db, child_user_id=user5.id, jnao_record_id="ra",
    answer_bitstring="0"*35, test_type=1,
    report={"talent": "学者", "create_time": "2026-06-28 14:00"})
row_b = save_assessment(db, child_user_id=user5.id, jnao_record_id="rb",
    answer_bitstring="1"*35, test_type=1,
    report={"talent": "行者", "create_time": "2026-06-28 14:30"})
check("5d. JNAO重测不冲突", not getattr(row_b, "_talent_conflict", False))
db.refresh(user5)
p5d = dict(user5.profile_json or {})
check("5e. JNAO重测自动更新", p5d.get("talent_code") == 3)

# Same talent assessment → no conflict
row_c = save_assessment(db, child_user_id=user5.id, jnao_record_id="rc",
    answer_bitstring="0"*35, test_type=1,
    report={"talent": "行者", "create_time": "2026-06-28 15:00"})
check("5f. 同天赋不冲突", not getattr(row_c, "_talent_conflict", False))

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} PASS, {FAIL} FAIL ({PASS+FAIL} total)")
print("=" * 60)

db.close()
if __name__ == "__main__":
    sys.exit(0 if FAIL == 0 else 1)
