"""
db/notify_models.py
整合訊息通知平台 SQLAlchemy ORM 模型（對應 V3__Create_notification_platform.sql）
沿用既有 db/session.py 的 Base / engine 慣例
"""
from __future__ import annotations
from datetime import datetime, date, time
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, Date,
    ForeignKey, Index, Integer, SmallInteger, String, Text,
    Time, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# 沿用既有 Base（來自 db/session.py 或 db/models.py）
try:
    from db.session import Base
except ImportError:
    from sqlalchemy.orm import DeclarativeBase
    class Base(DeclarativeBase):
        pass


class NotifyChannel(Base):
    __tablename__ = "notify_channel"

    channel_code         = Column(String(32), primary_key=True)
    channel_name         = Column(String(64), nullable=False)
    status               = Column(String(20), nullable=False, default="disabled")
    settings_enc         = Column(Text)
    capabilities         = Column(JSONB, nullable=False, default={})
    consecutive_failures = Column(Integer, nullable=False, default=0)
    circuit_open_until   = Column(Text)  # TIMESTAMPTZ stored as string for portability
    last_health_at       = Column(Text)
    created_at           = Column(Text, nullable=False, default=func.now())
    updated_at           = Column(Text, nullable=False, default=func.now())


class NotifyRecipient(Base):
    __tablename__ = "notify_recipient"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    recipient_code = Column(String(64), nullable=False, unique=True)
    display_name   = Column(String(128), nullable=False)
    status         = Column(String(20), nullable=False, default="active")
    created_at     = Column(Text, nullable=False, default=func.now())
    updated_at     = Column(Text, nullable=False, default=func.now())

    endpoints    = relationship("NotifyEndpoint", back_populates="recipient")
    preference   = relationship("NotifyRecipientPreference", back_populates="recipient", uselist=False)
    self_tokens  = relationship("NotifySelfServiceToken", back_populates="recipient")


class NotifyEndpoint(Base):
    __tablename__ = "notify_endpoint"

    id                   = Column(BigInteger, primary_key=True, autoincrement=True)
    endpoint_code        = Column(String(64), nullable=False, unique=True)
    channel_code         = Column(String(32), ForeignKey("notify_channel.channel_code"), nullable=False)
    recipient_id         = Column(BigInteger, ForeignKey("notify_recipient.id"))
    endpoint_scope       = Column(String(16), nullable=False, default="personal")
    address              = Column(String(512), nullable=False)
    verify_status        = Column(String(20), nullable=False, default="pending")
    status               = Column(String(20), nullable=False, default="active")
    delivery_mode        = Column(String(20), nullable=False, default="realtime")
    quiet_start          = Column(Time)
    quiet_end            = Column(Time)
    timezone             = Column(String(64), nullable=False, default="Asia/Taipei")
    daily_limit          = Column(Integer, nullable=False, default=30)
    digest_send_time     = Column(Time)
    pause_until          = Column(Text)
    fallback_endpoint_id = Column(BigInteger, ForeignKey("notify_endpoint.id"))
    created_at           = Column(Text, nullable=False, default=func.now())
    updated_at           = Column(Text, nullable=False, default=func.now())

    recipient = relationship("NotifyRecipient", back_populates="endpoints")
    messages  = relationship("NotifyMessage", back_populates="endpoint")


class NotifyGroup(Base):
    __tablename__ = "notify_group"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    group_code = Column(String(64), nullable=False, unique=True)
    group_name = Column(String(128), nullable=False)
    created_at = Column(Text, nullable=False, default=func.now())

    members = relationship("NotifyGroupMember", back_populates="group")


class NotifyGroupMember(Base):
    __tablename__ = "notify_group_member"
    __table_args__ = (UniqueConstraint("group_id", "recipient_id"),)

    group_id     = Column(BigInteger, ForeignKey("notify_group.id", ondelete="CASCADE"), primary_key=True)
    recipient_id = Column(BigInteger, ForeignKey("notify_recipient.id", ondelete="CASCADE"), primary_key=True)

    group     = relationship("NotifyGroup", back_populates="members")
    recipient = relationship("NotifyRecipient")


class NotifySubscription(Base):
    __tablename__ = "notify_subscription"

    id                  = Column(BigInteger, primary_key=True, autoincrement=True)
    rule_code           = Column(String(64), nullable=False, unique=True)
    rule_name           = Column(String(128), nullable=False)
    event_type          = Column(String(64), nullable=False)
    filter_conditions   = Column(JSONB, nullable=False, default={})
    target_group_id     = Column(BigInteger, ForeignKey("notify_group.id"))
    target_recipient_id = Column(BigInteger, ForeignKey("notify_recipient.id"))
    target_endpoint_id  = Column(BigInteger, ForeignKey("notify_endpoint.id"))
    status              = Column(String(20), nullable=False, default="enabled")
    priority            = Column(Integer, nullable=False, default=100)
    created_at          = Column(Text, nullable=False, default=func.now())
    updated_at          = Column(Text, nullable=False, default=func.now())


class NotifyEvent(Base):
    __tablename__ = "notify_event"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    event_uid       = Column(String(36), nullable=False, unique=True)
    idempotency_key = Column(String(256), nullable=False)
    event_type      = Column(String(64), nullable=False)
    severity        = Column(String(20), nullable=False)
    source          = Column(String(64), nullable=False)
    occurred_at     = Column(Text, nullable=False)
    received_at     = Column(Text, nullable=False, default=func.now())
    payload         = Column(JSONB, nullable=False, default={})
    routing_facts   = Column(JSONB, nullable=False, default={})
    routed_status   = Column(String(20), nullable=False, default="pending")

    messages = relationship("NotifyMessage", back_populates="event")


class NotifyMessage(Base):
    __tablename__ = "notify_message"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    message_code     = Column(String(128), nullable=False, unique=True)
    event_id         = Column(BigInteger, ForeignKey("notify_event.id"), nullable=False)
    endpoint_id      = Column(BigInteger, ForeignKey("notify_endpoint.id"), nullable=False)
    channel_code     = Column(String(32), nullable=False)
    idempotency_key  = Column(String(256), nullable=False)
    priority         = Column(SmallInteger, nullable=False, default=10)
    status           = Column(String(30), nullable=False, default="pending")
    subject          = Column(Text)
    body             = Column(Text, nullable=False, default="")
    scheduled_at     = Column(Text, nullable=False, default=func.now())
    attempt_count    = Column(Integer, nullable=False, default=0)
    next_retry_at    = Column(Text)
    claimed_at       = Column(Text)
    claimed_by       = Column(String(64))
    sent_at          = Column(Text)
    digest_message_id = Column(BigInteger, ForeignKey("notify_message.id"))
    last_failure_kind = Column(String(32))
    created_at       = Column(Text, nullable=False, default=func.now())
    updated_at       = Column(Text, nullable=False, default=func.now())

    event    = relationship("NotifyEvent", back_populates="messages")
    endpoint = relationship("NotifyEndpoint", back_populates="messages")
    logs     = relationship("NotifyDeliveryLog", back_populates="message")


class NotifyDeliveryLog(Base):
    __tablename__ = "notify_delivery_log"

    id                  = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id          = Column(BigInteger, ForeignKey("notify_message.id"), nullable=False)
    attempt_no          = Column(Integer, nullable=False)
    result              = Column(String(30), nullable=False)
    failure_kind        = Column(String(32))
    failure_reason      = Column(Text)
    provider_message_id = Column(String(256))
    latency_ms          = Column(Integer)
    attempted_at        = Column(Text, nullable=False, default=func.now())

    message = relationship("NotifyMessage", back_populates="logs")


class NotifyTemplate(Base):
    __tablename__ = "notify_template"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    template_code = Column(String(128), nullable=False, unique=True)
    event_type    = Column(String(64), nullable=False)
    channel_code  = Column(String(32), ForeignKey("notify_channel.channel_code"), nullable=False)
    title_format  = Column(Text)
    body_format   = Column(Text, nullable=False, default="")
    body_kind     = Column(String(16), nullable=False, default="text")
    is_default    = Column(Boolean, nullable=False, default=False)
    created_at    = Column(Text, nullable=False, default=func.now())
    updated_at    = Column(Text, nullable=False, default=func.now())


class NotifyBindingToken(Base):
    __tablename__ = "notify_binding_token"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    token_digest = Column(String(64), nullable=False, unique=True)
    purpose      = Column(String(32), nullable=False)
    channel_code = Column(String(32), nullable=False)
    endpoint_id  = Column(BigInteger, ForeignKey("notify_endpoint.id"))
    recipient_id = Column(BigInteger, ForeignKey("notify_recipient.id"))
    expires_at   = Column(Text, nullable=False)
    used_at      = Column(Text)
    created_at   = Column(Text, nullable=False, default=func.now())


class NotifySelfServiceToken(Base):
    __tablename__ = "notify_self_service_token"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    token_digest = Column(String(64), nullable=False, unique=True)
    recipient_id = Column(BigInteger, ForeignKey("notify_recipient.id"), nullable=False)
    status       = Column(String(16), nullable=False, default="active")
    revoked_at   = Column(Text)
    last_used_at = Column(Text)
    created_at   = Column(Text, nullable=False, default=func.now())

    recipient = relationship("NotifyRecipient", back_populates="self_tokens")


class NotifyRecipientPreference(Base):
    __tablename__ = "notify_recipient_preference"

    recipient_id                = Column(BigInteger, ForeignKey("notify_recipient.id"), primary_key=True)
    allowed_markets             = Column(JSONB, nullable=False, default=["tw", "us"])
    allowed_strengths           = Column(JSONB, nullable=False, default=["strong", "moderate", "weak"])
    allowed_signal_types        = Column(JSONB, nullable=False, default=["BUY", "SELL", "WARNING"])
    allowed_strategy_categories = Column(JSONB, nullable=False, default=["technical", "chip", "fundamental"])
    watch_symbols               = Column(JSONB)
    updated_at                  = Column(Text, nullable=False, default=func.now())

    recipient = relationship("NotifyRecipient", back_populates="preference")


class NotifyPreferenceAudit(Base):
    __tablename__ = "notify_preference_audit"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    recipient_id   = Column(BigInteger, ForeignKey("notify_recipient.id"), nullable=False)
    actor          = Column(String(64), nullable=False, default="self")
    change_summary = Column(JSONB, nullable=False, default={})
    changed_at     = Column(Text, nullable=False, default=func.now())


class NotifyQuotaUsage(Base):
    __tablename__ = "notify_quota_usage"
    __table_args__ = (UniqueConstraint("scope", "scope_key", "usage_date"),)

    scope      = Column(String(32), primary_key=True)
    scope_key  = Column(String(128), primary_key=True)
    usage_date = Column(Date, primary_key=True)
    used_count = Column(Integer, nullable=False, default=0)


class NotifySuppression(Base):
    __tablename__ = "notify_suppression"

    cooldown_key     = Column(String(128), primary_key=True)
    first_seen_at    = Column(Text, nullable=False, default=func.now())
    last_seen_at     = Column(Text, nullable=False, default=func.now())
    occurrence_count = Column(Integer, nullable=False, default=1)
    cooldown_until   = Column(Text, nullable=False)


class NotifyAdminAudit(Base):
    __tablename__ = "notify_admin_audit"

    id       = Column(BigInteger, primary_key=True, autoincrement=True)
    actor    = Column(String(64), nullable=False, default="owner")
    action   = Column(String(128), nullable=False)
    target   = Column(String(256))
    result   = Column(String(16), nullable=False)
    detail   = Column(JSONB)
    acted_at = Column(Text, nullable=False, default=func.now())
