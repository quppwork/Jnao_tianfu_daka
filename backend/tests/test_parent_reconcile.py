"""家长—孩子绑定对账测试"""

from fastapi.testclient import TestClient

from app.core.password import hash_password
from app.services import auth_service
from app.services.parent_reconcile_service import (
    find_unbound_students_by_phone,
    reconcile_parent_children,
    resolve_canonical_parent,
)


def _seed_parent(db_session, phone: str, nickname: str, *, child_quota: int = 5) -> int:
    user = auth_service.register_child(
        db_session,
        parent_phone=phone,
        nickname=nickname,
        password=hash_password("123456"),
        role=auth_service.ROLE_PARENT,
        child_quota=child_quota,
    )
    return user.id


def _seed_orphan_student(db_session, phone: str, login_name: str, nickname: str) -> int:
    user = auth_service.register_child(
        db_session,
        parent_phone=phone,
        nickname=nickname,
        login_name=login_name,
        password=hash_password("111111"),
        role=auth_service.ROLE_STUDENT,
    )
    return user.id


class TestParentReconcile:
    def test_reconcile_binds_orphan_student(self, db_session):
        phone = "13900008801"
        pid = _seed_parent(db_session, phone, "家长A")
        cid = _seed_orphan_student(db_session, phone, "orphan1", "孤儿童")

        assert auth_service.count_parent_children(db_session, pid) == 0
        assert len(find_unbound_students_by_phone(db_session, phone)) == 1

        bound = reconcile_parent_children(db_session, pid)
        assert bound == 1
        assert auth_service.count_parent_children(db_session, pid) == 1
        assert find_unbound_students_by_phone(db_session, phone) == []

    def test_parent_list_does_not_auto_reconcile(self, client: TestClient, db_session):
        phone = "13900008802"
        pid = _seed_parent(db_session, phone, "家长B")
        _seed_orphan_student(db_session, phone, "orphan2", "孤儿童2")

        res = client.get(f"/api/parent/children?user_id={pid}")
        assert res.status_code == 200
        kids = res.json()["children"]
        assert len(kids) == 0

    def test_admin_reconcile_binds_orphan(self, client: TestClient, db_session):
        from tests.test_admin_api import _admin_login, _auth_admin

        phone = "13900008803"
        pid = _seed_parent(db_session, phone, "家长C")
        _seed_orphan_student(db_session, phone, "orphan3", "孤儿童3")

        admin = _admin_login(client)
        auth = _auth_admin(admin)
        detail = client.get(f"/api/admin/parents/{pid}/detail", **auth)
        assert detail.status_code == 200
        data = detail.json()
        assert data["pending_unbound_count"] == 1
        assert len(data["unbound_children"]) == 1
        assert len(data["children"]) == 0

        rec = client.post(f"/api/admin/parents/{pid}/reconcile", **auth)
        assert rec.status_code == 200
        assert rec.json()["reconciled_count"] == 1
        assert len(rec.json()["children"]) == 1

    def test_admin_detail_shows_unbound_before_reconcile(self, client: TestClient, db_session):
        from tests.test_admin_api import _admin_login, _auth_admin

        phone = "13900008831"
        pid = _seed_parent(db_session, phone, "家长C2")
        _seed_orphan_student(db_session, phone, "orphan31", "孤儿童31")

        admin = _admin_login(client)
        auth = _auth_admin(admin)
        res = client.get(f"/api/admin/parents/{pid}/detail", **auth)
        assert res.status_code == 200
        data = res.json()
        assert data["reconciled_count"] == 0
        assert data["pending_unbound_count"] == 1
        assert len(data["unbound_children"]) == 1
        assert data["unbound_children"][0]["login_name"] == "orphan31"

    def test_duplicate_parent_shows_canonical_children(self, db_session, client: TestClient):
        from app.db.models import ChildUser
        from tests.test_admin_api import _admin_login, _auth_admin

        phone = "13900008804"
        pid1 = _seed_parent(db_session, phone, "家长主")
        pid2 = ChildUser(
            parent_phone=phone,
            nickname="家长副",
            role=auth_service.ROLE_PARENT,
            password_hash=hash_password("123456"),
            child_quota=5,
            session_token=auth_service._generate_session_token(),
        )
        db_session.add(pid2)
        db_session.commit()
        db_session.refresh(pid2)
        pid2 = pid2.id
        cid = _seed_orphan_student(db_session, phone, "dupkid", "重复童")
        auth_service.bind_parent_child(db_session, pid1, cid)

        canonical = resolve_canonical_parent(db_session, phone)
        assert canonical is not None
        assert canonical.id in (pid1, pid2)

        admin = _admin_login(client)
        auth = _auth_admin(admin)
        for view_id in (pid1, pid2):
            res = client.get(f"/api/admin/parents/{view_id}/detail", **auth)
            assert res.status_code == 200
            data = res.json()
            assert len(data["children"]) == 1
            assert data["children"][0]["login_name"] == "dupkid"
            assert data["canonical_parent_id"] == canonical.id
            if view_id != canonical.id:
                assert data["is_duplicate_account"] is True
