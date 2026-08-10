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
    login_name: Mapped[str | None] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(10), default="student")
    child_quota: Mapped[int | None] = mapped_column(Integer)
    jnao_uid: Mapped[str | None] = mapped_column(String(50))
    profile_json: Mapped[dict | None] = mapped_column(JSON)
    training_level: Mapped[str | None] = mapped_column(String(20))
    is_qingbei: Mapped[int] = mapped_column(Integer, default=0)
    session_token: Mapped[str | None] = mapped_column(String(64))
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    assessments: Mapped[list["TalentAssessment"]] = relationship(back_populates="child_user")
    training_plans: Mapped[list["TrainingPlan"]] = relationship(back_populates="child_user")
    parent_binds: Mapped[list["ParentChildBind"]] = relationship(
        back_populates="parent",
        foreign_keys="ParentChildBind.parent_id",
    )
    child_binds: Mapped[list["ParentChildBind"]] = relationship(
        back_populates="child",
        foreign_keys="ParentChildBind.child_id",
    )


class WxMemberSnapshot(Base):
    """从 db_fz_jingnao.ys_wx_member 同步的微信会员镜像（只读对照，不写入老库）"""

    __tablename__ = "wx_member_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wx_member_id: Mapped[int | None] = mapped_column(Integer)
    openid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    unionid: Mapped[str | None] = mapped_column(String(64))
    mobile: Mapped[str | None] = mapped_column(String(20))
    nickname: Mapped[str | None] = mapped_column(String(255))
    truename: Mapped[str | None] = mapped_column(String(64))
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DakaMember(Base):
    """本平台注册家长会员 — 短信/密码/微信登录写入，登录优先查此表"""

    __tablename__ = "daka_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False, unique=True)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    openid: Mapped[str | None] = mapped_column(String(64), unique=True)
    unionid: Mapped[str | None] = mapped_column(String(64))
    register_channel: Mapped[str] = mapped_column(String(20), nullable=False)
    legacy_matched: Mapped[int] = mapped_column(Integer, default=0)
    legacy_wx_member_id: Mapped[int | None] = mapped_column(Integer)
    real_name: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(50))
    registered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    wechat_bound_at: Mapped[datetime | None] = mapped_column(DateTime)
    company_verified_at: Mapped[datetime | None] = mapped_column(DateTime)


class ParentWechatBind(Base):
    """微信 openid 与 Jnao 家长账号绑定"""

    __tablename__ = "parent_wechat_bind"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    openid: Mapped[str] = mapped_column(String(64), nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(64))
    wx_member_id: Mapped[int | None] = mapped_column(Integer)
    app_id: Mapped[str] = mapped_column(String(32), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class ParentChildBind(Base):
    __tablename__ = "parent_child_bind"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    child_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    parent: Mapped["ChildUser"] = relationship(
        back_populates="parent_binds",
        foreign_keys=[parent_id],
    )
    child: Mapped["ChildUser"] = relationship(
        back_populates="child_binds",
        foreign_keys=[child_id],
    )


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
    media_exhausted: Mapped[int] = mapped_column(Integer, default=0)
    plan_customized: Mapped[int] = mapped_column(Integer, default=0)
    # Agent 辅助排课调试信息（理由/草案等）；正式 UI 不展示
    schedule_assist_json: Mapped[dict | None] = mapped_column(JSON)
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
    watch_progress: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plan: Mapped["TrainingPlan"] = relationship(back_populates="items")


class TrainingRecord(Base):
    __tablename__ = "training_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(Integer)
    item_id: Mapped[int | None] = mapped_column(Integer)
    train_date: Mapped[date | None] = mapped_column(Date)
    ability_type: Mapped[str | None] = mapped_column(String(20))
    time_spent: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    attitude_pct: Mapped[int | None] = mapped_column(Integer)
    files_json: Mapped[dict | list | None] = mapped_column(JSON)
    # 预留：家长/运营复核打卡质量（暂无 API，默认 approved）
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
    # 会话级轻量记忆：rolling_summary 等（删会话即清空）
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["QaMessage"]] = relationship(
        back_populates="session",
        order_by="QaMessage.id",
        cascade="all, delete-orphan",
    )


class QaMessage(Base):
    __tablename__ = "qa_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("qa_session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 预留：语音提问/回复（当前仅文本+图片答疑）
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
        back_populates="session", order_by="GuideMessage.id",
        cascade="all, delete-orphan",
    )


class GuideMessage(Base):
    __tablename__ = "guide_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("guide_session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # assistant：actions / tools_used（历史回放用）；user 一般为 null
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["GuideSession"] = relationship(back_populates="messages")


class QaSessionArchive(Base):
    """学科答疑会话归档 — 超期会话快照，主表删除后供审计与统计"""

    __tablename__ = "qa_session_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GuideSessionArchive(Base):
    """首页引导会话归档 — 超期会话快照"""

    __tablename__ = "guide_session_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSession(Base):
    """登录会话 — 支持按角色限制多端数量"""

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
