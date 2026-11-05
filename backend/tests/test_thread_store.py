"""统一 ThreadStore：报告会话按 assessment_id 隔离。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, TalentAssessment
from app.memory import ThreadRef, get_thread_store
from app.memory.protocols import DOMAIN_REPORT_TALENT


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_report_threads_are_isolated():
    db = _db()
    u1 = ChildUser(parent_phone="13900000001", nickname="a", role="student", password_hash="x")
    u2 = ChildUser(parent_phone="13900000002", nickname="b", role="student", password_hash="x")
    db.add_all([u1, u2])
    db.flush()
    a = TalentAssessment(child_user_id=u1.id, test_type=0, talent_primary="学者")
    b = TalentAssessment(child_user_id=u2.id, test_type=0, talent_primary="思者")
    db.add_all([a, b])
    db.commit()

    store = get_thread_store(db)
    ra = ThreadRef(DOMAIN_REPORT_TALENT, u1.id, str(a.id))
    rb = ThreadRef(DOMAIN_REPORT_TALENT, u2.id, str(b.id))

    store.append_pair(ra, user_content="学者问", assistant_content="学者答")
    store.append_pair(rb, user_content="思者问", assistant_content="思者答")

    ma = store.list_messages(ra)
    mb = store.list_messages(rb)
    assert [m.content for m in ma] == ["学者问", "学者答"]
    assert [m.content for m in mb] == ["思者问", "思者答"]

    n = store.clear(ra)
    assert n == 2
    assert store.list_messages(ra) == []
    assert len(store.list_messages(rb)) == 2
    db.close()
