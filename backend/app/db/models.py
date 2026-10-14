"""ORM models — 表结构真源；唯一键/索引需与线上及 migrate 幂等补丁一致。"""

from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
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
    __table_args__ = (
        Index("idx_wx_snapshot_mobile", "mobile"),
        Index("idx_wx_snapshot_unionid", "unionid"),
    )

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
    __table_args__ = (
        UniqueConstraint("openid", "app_id", name="uk_wechat_openid_app"),
        UniqueConstraint("parent_id", "app_id", name="uk_wechat_parent_app"),
    )

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
    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uk_parent_child"),
        UniqueConstraint("child_id", name="uk_parent_child_child_id"),
    )

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
    __table_args__ = (Index("idx_talent_assessment_user", "child_user_id"),)

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
    __table_args__ = (Index("idx_content_talent_sort", "talent_code", "lesson_sort"),)

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
    __table_args__ = (
        UniqueConstraint("child_user_id", "plan_date", name="uk_training_plan_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    level: Mapped[str | None] = mapped_column(String(20))
    report_text: Mapped[str | None] = mapped_column(Text)
    planned_minutes: Mapped[int | None] = mapped_column(Integer)
    content_index: Mapped[int] = mapped_column(Integer, default=0)
    media_exhausted: Mapped[int] = mapped_column(Integer, default=0)
    plan_customized: Mapped[int] = mapped_column(Integer, default=0)
    # 历史列：曾用于 Agent 辅助排课调试；功能已下线，保留兼容旧库
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
    __table_args__ = (
        Index("idx_record_user_date", "child_user_id", "train_date"),
        Index("idx_record_plan", "plan_id"),
        Index("idx_record_item", "item_id"),
    )

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
    __table_args__ = (
        UniqueConstraint("child_user_id", "train_date", name="uk_training_window_user_date"),
        Index("idx_training_window_user", "child_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    train_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QaSession(Base):
    __tablename__ = "qa_session"
    __table_args__ = (Index("idx_qa_session_user", "child_user_id"),)

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
    __table_args__ = (Index("idx_guide_session_user", "child_user_id"),)

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
    __table_args__ = (
        Index("idx_qa_archive_user_time", "child_user_id", "archived_at"),
        Index("idx_qa_archive_orig", "original_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GuideSessionArchive(Base):
    """首页引导会话归档 — 超期会话快照"""

    __tablename__ = "guide_session_archive"
    __table_args__ = (
        Index("idx_guide_archive_user_time", "child_user_id", "archived_at"),
        Index("idx_guide_archive_orig", "original_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSession(Base):
    """登录会话 — 支持按角色限制多端数量"""

    __tablename__ = "user_session"
    __table_args__ = (
        Index("idx_user_session_user", "user_id"),
        Index("idx_user_session_last_active", "last_active_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("child_user.id"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UpstreamUsageEvent(Base):
    """上游用量明细 — 按操作者 user_id 分计；billing_parent_id 供家长汇总算账"""

    __tablename__ = "upstream_usage_event"
    __table_args__ = (
        Index("idx_usage_user_created", "user_id", "created_at"),
        Index("idx_usage_billing_parent_created", "billing_parent_id", "created_at"),
        Index("idx_usage_provider_created", "provider", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    api: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    feature: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    billing_parent_id: Mapped[int | None] = mapped_column(Integer, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    metric_kind: Mapped[str] = mapped_column(String(16), default="tokens")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    call_count: Mapped[int] = mapped_column(Integer, default=1)
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    stream: Mapped[int] = mapped_column(Integer, default=0)
    estimated: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CreditAccount(Base):
    """算力账本（挂在家长账户）— 会员月度额度 + 充值余额。

    用量明细仍在 upstream_usage_event；本表管「可消耗额度 / 余额」。
    """

    __tablename__ = "credit_account"
    __table_args__ = (
        UniqueConstraint("owner_user_id", name="uq_credit_account_owner"),
        Index("idx_credit_account_owner", "owner_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 充值余额，单位：分
    balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    # free | lite | plus | pro | flagship
    plan_code: Mapped[str] = mapped_column(String(32), default="free")
    monthly_quota_points: Mapped[int] = mapped_column(Integer, default=1000)
    # 当前计费月 YYYY-MM（CST）；换月时重置额度占用
    period_yyyy_mm: Mapped[str] = mapped_column(String(7), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CreditLedger(Base):
    """算力账变明细 — 充值 / 消耗 / 赠送 / 月重置 / 调账。"""

    __tablename__ = "credit_ledger"
    __table_args__ = (
        Index("idx_credit_ledger_owner_created", "owner_user_id", "created_at"),
        Index("idx_credit_ledger_kind_created", "kind", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # topup | consume | grant | reset | adjust | membership
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    points_delta: Mapped[int] = mapped_column(Integer, default=0)
    cents_delta: Mapped[int] = mapped_column(Integer, default=0)
    balance_cents_after: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(200))
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[str | None] = mapped_column(String(64))
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CreditProductOrder(Base):
    """算力商品订单（会员 / 充值包）— 支付通道后置，先落单。"""

    __tablename__ = "credit_product_order"
    __table_args__ = (
        Index("idx_credit_order_owner_created", "owner_user_id", "created_at"),
        Index("idx_credit_order_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(64), nullable=False)
    # membership | topup
    product_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    # pending | paid | cancelled | failed
    status: Mapped[str] = mapped_column(String(16), default="pending")
    pay_channel: Mapped[str | None] = mapped_column(String(32))
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)


class AcademyProgress(Base):
    """天赋学院单集观看进度。解锁只看服务端 percent，不信前端计时。"""

    __tablename__ = "academy_progress"
    __table_args__ = (
        UniqueConstraint("child_user_id", "episode_id", name="uk_academy_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[str] = mapped_column(String(16), nullable=False)
    percent: Mapped[int] = mapped_column(Integer, default=0)
    unlocked: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AcademyRoom(Base):
    """讨论区记录。每人独立，角色台词由学院 harness 写入。"""

    __tablename__ = "academy_room"
    __table_args__ = (
        UniqueConstraint("child_user_id", "episode_id", name="uk_academy_room"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[str] = mapped_column(String(16), nullable=False)
    messages: Mapped[list | None] = mapped_column(JSON)
    user_turns: Mapped[int] = mapped_column(Integer, default=0)
    affect: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AcademyBot(Base):
    """画中人。bot_id 稳定，提示词和约束可改，六个角色同一张表。"""

    __tablename__ = "academy_bot"

    bot_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    character_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    tag: Mapped[str] = mapped_column(String(16), nullable=False)
    persona_prompt: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    voice: Mapped[str] = mapped_column(Text, default="")
    steer: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AcademyBotScript(Base):
    """某个 Bot 眼中的某一集剧本和剧情。不与其他 Bot 共用正文。"""

    __tablename__ = "academy_bot_script"
    __table_args__ = (
        UniqueConstraint("bot_id", "episode_id", name="uk_academy_bot_script"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    episode_id: Mapped[str] = mapped_column(String(16), nullable=False)
    script_body: Mapped[str] = mapped_column(Text, default="")
    plot_summary: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # PRD 版本化：draft | published | disabled
    content_version: Mapped[str] = mapped_column(String(32), default="v1")
    publish_status: Mapped[str] = mapped_column(String(16), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AcademyBotMemory(Base):
    """长期自我感知。每次提示词、约束、剧本、剧情更新追加一条，不覆盖。"""

    __tablename__ = "academy_bot_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    episode_id: Mapped[str | None] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AcademyBotSession(Base):
    """某个 Bot 在某孩子、某集讨论里的会话记忆。与别人的会话记忆分开。"""

    __tablename__ = "academy_bot_session"
    __table_args__ = (
        UniqueConstraint("bot_id", "child_user_id", "episode_id", name="uk_academy_bot_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    child_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    episode_id: Mapped[str] = mapped_column(String(16), nullable=False)
    messages: Mapped[list | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ── 在线咨询（consult_*；与 guide_* 分离）────────────────────────────────


class ConsultChannel(Base):
    """咨询频道目录：大宇群 / 顾问 DM。"""

    __tablename__ = "consult_channel"
    __table_args__ = (Index("idx_consult_channel_status_sort", "status", "sort_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # group | dm
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    bot_persona: Mapped[str | None] = mapped_column(String(64))
    im_group_template: Mapped[str | None] = mapped_column(String(128))
    advisor_user_id: Mapped[int | None] = mapped_column(Integer)
    ai_enabled: Mapped[int] = mapped_column(Integer, default=1)
    human_handoff: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list["ConsultConversation"]] = relationship(
        back_populates="channel"
    )


class ConsultConversation(Base):
    """一次进线会话（业务主键；IM 会话 ID 可空）。"""

    __tablename__ = "consult_conversation"
    __table_args__ = (
        Index("idx_consult_conv_parent", "parent_user_id", "updated_at"),
        Index("idx_consult_conv_assignee", "assignee_id", "status"),
        Index("idx_consult_conv_channel_parent", "channel_id", "parent_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("consult_channel.id"), nullable=False
    )
    parent_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_user_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    im_conversation_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="open")
    assignee_id: Mapped[int | None] = mapped_column(Integer)
    last_msg_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_msg_preview: Mapped[str | None] = mapped_column(String(200))
    unread_parent: Mapped[int] = mapped_column(Integer, default=0)
    unread_advisor: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    channel: Mapped["ConsultChannel"] = relationship(back_populates="conversations")
    members: Mapped[list["ConsultMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["ConsultMessage"]] = relationship(
        back_populates="conversation",
        order_by="ConsultMessage.id",
        cascade="all, delete-orphan",
    )


class ConsultMember(Base):
    __tablename__ = "consult_member"
    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", "role", name="uk_consult_member"),
        Index("idx_consult_member_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("consult_conversation.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    im_user_id: Mapped[str | None] = mapped_column(String(128))
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime)

    conversation: Mapped["ConsultConversation"] = relationship(back_populates="members")


class ConsultMessage(Base):
    """消息真相源。"""

    __tablename__ = "consult_message"
    __table_args__ = (
        UniqueConstraint("im_msg_id", name="uk_consult_msg_im"),
        UniqueConstraint("conversation_id", "client_msg_id", name="uk_consult_msg_client"),
        Index("idx_consult_msg_conv_id", "conversation_id", "id"),
        Index("idx_consult_msg_conv_time", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("consult_conversation.id"), nullable=False
    )
    client_msg_id: Mapped[str | None] = mapped_column(String(64))
    im_msg_id: Mapped[str | None] = mapped_column(String(128))
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_user_id: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(16), default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    reply_to_id: Mapped[int | None] = mapped_column(Integer)
    visibility: Mapped[str] = mapped_column(String(16), default="all")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["ConsultConversation"] = relationship(back_populates="messages")


class ConsultAgentJob(Base):
    __tablename__ = "consult_agent_job"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uk_consult_job_idem"),
        Index("idx_consult_job_status", "status", "id"),
        Index("idx_consult_job_conv", "conversation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("consult_conversation.id"), nullable=False
    )
    trigger_msg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    intent: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    kb_hits_json: Mapped[dict | list | None] = mapped_column(JSON)
    tool_trace_json: Mapped[dict | list | None] = mapped_column(JSON)
    result_msg_id: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConsultAdvisorPresence(Base):
    __tablename__ = "consult_advisor_presence"

    advisor_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_online: Mapped[int] = mapped_column(Integer, default=0)
    im_online: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=5)
    active_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ConsultBoardPost(Base):
    __tablename__ = "consult_board_post"
    __table_args__ = (
        Index("idx_consult_board_channel", "channel_id", "status"),
        Index("idx_consult_board_parent", "parent_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("consult_channel.id"), nullable=False
    )
    parent_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open")
    claimed_by: Mapped[int | None] = mapped_column(Integer)
    reply_body: Mapped[str | None] = mapped_column(Text)
    reply_msg_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AcademicPlanConfirm(Base):
    """已确认学业规划（PRD §4.3）— 个性化学科引导的前置。"""

    __tablename__ = "academic_plan_confirm"
    __table_args__ = (
        Index("idx_academic_plan_confirm_user", "child_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    child_user_id: Mapped[int] = mapped_column(
        ForeignKey("child_user.id"), nullable=False, unique=True
    )
    # draft | confirmed | expired
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    target_subject: Mapped[str | None] = mapped_column(String(64))
    target_ability: Mapped[str | None] = mapped_column(String(64))
    current_level: Mapped[str | None] = mapped_column(String(64))
    stage_goal: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="growth_ai")
    author: Mapped[str | None] = mapped_column(String(64))
    plan_json: Mapped[dict | None] = mapped_column(JSON)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class HarnessEvidenceRow(Base):
    """Harness 工具 Evidence 账本（持久化）。"""

    __tablename__ = "harness_evidence"
    __table_args__ = (
        Index("idx_harness_evidence_tool_created", "tool", "created_at"),
        Index("idx_harness_evidence_sha", "content_sha256"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    profile: Mapped[str] = mapped_column(String(32), default="")
    ok: Mapped[int] = mapped_column(Integer, default=1)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
