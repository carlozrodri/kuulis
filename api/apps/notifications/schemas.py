import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.notifications.models import Platform
from apps.users.models import Role


class DeviceRegister(BaseModel):
    push_token: str = Field(min_length=10, max_length=255)
    platform: Platform
    app_version: str | None = Field(default=None, max_length=32)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    app_version: str | None
    is_active: bool
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    data: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationSend(BaseModel):
    """Admin panel: send to one user, a role, or everyone."""

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=2000)
    data: dict[str, Any] = Field(default_factory=dict)
    user_id: uuid.UUID | None = None
    role: Role | None = None


class UnreadCount(BaseModel):
    unread: int
