"""家长课堂目录：配置可加载、API 形状稳定。"""

from app.services import auth_service
from app.services.parent_course_service import list_courses
from config.loader import load_parent_courses


def test_load_parent_courses_yaml():
    cfg = load_parent_courses()
    assert cfg.get("version") == 1
    courses = cfg.get("courses") or []
    assert len(courses) >= 6
    ids = {c.get("id") for c in courses}
    assert "parent_relation" in ids
    assert "tools" in ids


def test_list_courses_shape(db_session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900001101",
        nickname="课堂家长",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    db_session.commit()
    data = list_courses(db_session, parent.id)
    assert data["title"]
    assert data["opened_count"] == len(data["courses"])
    assert data["courses"]
    first = data["courses"][0]
    assert first["id"]
    assert first["name"]
    assert isinstance(first["lessons"], list)
    assert first["total"] == len(first["lessons"])
    assert first["done"] == 0
    assert first["playback_ready"] is False


def test_parent_courses_api(client, db_session):
    parent = auth_service.register_child(
        db_session,
        parent_phone="13900001102",
        nickname="课堂家长二",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    db_session.commit()
    res = client.get(f"/api/parent/courses?user_id={parent.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["opened_count"] >= 6
    assert any(c["id"] == "parent_relation" for c in body["courses"])
