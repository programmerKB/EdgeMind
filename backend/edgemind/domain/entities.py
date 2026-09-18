"""Framework-independent entities shared by domain and application layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SensorReading:
    """One complete sensor snapshot without ORM or API framework behavior."""

    motor_id: str
    temperature: float
    humidity: float
    accel_x: float
    accel_y: float
    accel_z: float
    vibration: float
    status: str
    recorded_at: datetime | None = None
    id: int | None = None


@dataclass(frozen=True, slots=True)
class ChatConversation:
    """One shared conversation summary."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One persisted item in the visible chat timeline."""

    id: int
    role: str
    content: str
    status: str | None
    attachments: list[dict]
    token_usage: dict | None
    created_at: datetime
