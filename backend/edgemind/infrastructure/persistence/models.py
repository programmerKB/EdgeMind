"""SQLAlchemy persistence models.

Models describe storage only; querying and orchestration live in repositories
and services so HTTP handlers do not accumulate database rules.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.sql import func
from edgemind.infrastructure.persistence.database import Base


class MotorSensorData(Base):
    """One timestamped environmental feature vector from an edge device."""

    __tablename__ = "motor_sensor_data"
    __table_args__ = (
        Index("ix_motor_sensor_motor_recorded_at", "motor_id", "recorded_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    motor_id = Column(String, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    accel_x = Column(Float)
    accel_y = Column(Float)
    accel_z = Column(Float)
    # Keep the legacy aggregate vibration field for deployed edge clients.
    vibration = Column(Float)
    status = Column(String)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class TemperatureForecastModel(Base):
    """Latest persisted 30-minute forecast model for one training device."""

    __tablename__ = "temperature_forecast_models"

    id = Column(Integer, primary_key=True, index=True)
    motor_id = Column(String, unique=True, index=True, nullable=False)
    model_json = Column(Text, nullable=False)
    sample_count = Column(Integer, nullable=False)
    mae = Column(Float)
    rmse = Column(Float)
    trained_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


def utc_now() -> datetime:
    """Use one timezone-aware clock for chat ordering."""
    return datetime.now(timezone.utc)


class ChatConversationRow(Base):
    """Conversation metadata shared across browser sessions."""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_owner_updated", "owner_id", "updated_at"),
    )

    id = Column(String(36), primary_key=True)
    # Keep the existing column so old PostgreSQL volumes need no table rewrite.
    owner_id = Column(String(36), nullable=False)
    title = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ChatMessageRow(Base):
    """A user prompt or one Agent SSE event in its original order."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conversation_id", "conversation_id", "id"),
    )

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        String(36),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(30))
    attachments = Column(JSON, nullable=False, default=list)
    token_usage = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
