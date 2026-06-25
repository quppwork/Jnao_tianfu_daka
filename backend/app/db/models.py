"""ORM models — 对应 migrations/001_mvp.sql"""

from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChildUser(Base):
    __tablename__ = "child_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    jnao_uid: Mapped[str | None] = mapped_column(String(50))
    profile_json: Mapped[dict | None] = mapped_column(JSON)
    training_level: Mapped[str | None] = mapped_column(String(20))
    is_qingbei: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    assessments: Mapped[list["TalentAssessment"]] = relationship(back_populates="child_user")
    training_plans: Mapped[list["TrainingPlan"]] = relationship(back_populates="child_user")


class TalentAssessment(Base):
    __tablename__ = "talent_assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    jnao_record_id: Mapped[str | None] = mapped_column(String(50))
    answer_bitstring: Mapped[str | None] = mapped_column(String(35))
    test_type: Mapped[int] = mapped_column(Integer, default=1)
    talent_primary: Mapped[str | None] = mapped_column(String(20))
    talent_tag: Mapped[str | None] = mapped_column(String(5))
    talent_code: Mapped[int | None] = mapped_column(Integer)
    report_json: Mapped[dict | None] = mapped_column(JSON)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    child_user: Mapped["ChildUser"] = relationship(back_populates="assessments")


class TalentAssessmentArchive(Base):
    """已删除测评归档 — 供恢复与审计，主表删除后保留快照"""

    __tablename__ = "talent_assessment_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ContentItem(Base):
    __tablename__ = "content_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(Integer)
    course_id: Mapped[int | None] = mapped_column(Integer)
    talent_code: Mapped[int] = mapped_column(Integer, nullable=False)
    talent_tag: Mapped[str | None] = mapped_column(String(5))
    lesson_title: Mapped[str | None] = mapped_column(String(200))
    lesson_sort: Mapped[int] = mapped_column(Integer, default=0)
    play_url: Mapped[str] = mapped_column(String(500), nullable=False)
    video_url: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(10), default="audio")
    duration_min: Mapped[int | None] = mapped_column(Integer)
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TrainingPlan(Base):
    __tablename__ = "training_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    level: Mapped[str | None] = mapped_column(String(20))
    report_text: Mapped[str | None] = mapped_column(Text)
    planned_minutes: Mapped[int | None] = mapped_column(Integer)
    content_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    child_user: Mapped["ChildUser"] = relationship(back_populates="training_plans")
    items: Mapped[list["TrainingItem"]] = relationship(
        back_populates="plan", order_by="TrainingItem.sort_order"
    )


class TrainingItem(Base):
    __tablename__ = "training_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plan.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    ability_type: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    video_url: Mapped[str | None] = mapped_column(String(500))
    audio_url: Mapped[str | None] = mapped_column(String(500))
    instructions: Mapped[str | None] = mapped_column(Text)
    content_item_id: Mapped[int | None] = mapped_column(Integer)
    checkin_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plan: Mapped["TrainingPlan"] = relationship(back_populates="items")


class TrainingRecord(Base):
    __tablename__ = "training_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(Integer)
    item_id: Mapped[int | None] = mapped_column(Integer)
    ability_type: Mapped[str | None] = mapped_column(String(20))
    time_spent: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    attitude_pct: Mapped[int | None] = mapped_column(Integer)
    files_json: Mapped[dict | list | None] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(20), default="approved")
    reviewed_by: Mapped[int | None] = mapped_column(Integer)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TrainingWindow(Base):
    __tablename__ = "training_window"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    train_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QaSession(Base):
    __tablename__ = "qa_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["QaMessage"]] = relationship(
        back_populates="session", order_by="QaMessage.id"
    )


class QaMessage(Base):
    __tablename__ = "qa_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("qa_session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    voice_url: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["QaSession"] = relationship(back_populates="messages")


class GuideSession(Base):
    __tablename__ = "guide_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["GuideMessage"]] = relationship(
        back_populates="session", order_by="GuideMessage.id"
    )


class GuideMessage(Base):
    __tablename__ = "guide_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("guide_session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["GuideSession"] = relationship(back_populates="messages")
