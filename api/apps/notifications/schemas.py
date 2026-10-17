import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.notifications.models import CampaignStatus, Category, Platform
from apps.users.models import Role

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"
CHANNEL_ID = r"^[a-z][a-z0-9_]{0,39}$"


class DeviceRegister(BaseModel):
    push_token: str = Field(min_length=10, max_length=255)
    platform: Platform
    app_version: str | None = Field(default=None, max_length=32)
    # Android channels the app created (doc 14); older apps send nothing.
    channels: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("channels")
    @classmethod
    def _channels(cls, value: list[str]) -> list[str]:
        import re

        return [c for c in dict.fromkeys(value) if re.match(CHANNEL_ID, c)]


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
    category: Category
    deep_link: str | None
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


# --- Preferences (doc 14) -----------------------------------------------------------------------


class PreferencesRead(BaseModel):
    """Only marketing can be turned off; ride, wallet, account, support and safety notices
    always arrive. Quiet hours (Caracas time) hold marketing back."""

    marketing_push: bool
    marketing_email: bool
    demand_alerts: bool = True  # drivers: pushes when a zone nearby gets busy (doc 21)
    quiet_start: str
    quiet_end: str
    default_quiet_start: str
    default_quiet_end: str


class PreferencesUpdate(BaseModel):
    marketing_push: bool | None = None
    marketing_email: bool | None = None
    demand_alerts: bool | None = None
    quiet_start: str | None = Field(default=None, pattern=HHMM)
    quiet_end: str | None = Field(default=None, pattern=HHMM)


# --- Campaigns (doc 14) -------------------------------------------------------------------------

Audience = Literal["all", "passengers", "drivers"]
CampaignChannel = Literal["push", "inbox", "email"]


class Segment(BaseModel):
    """Who gets a campaign. Every condition narrows the audience (AND)."""

    audience: Audience = "all"
    # Service area names (settings). Drivers by their city, passengers by where they rode in
    # the last 90 days. Empty = everywhere.
    cities: list[str] = Field(default_factory=list, max_length=20)
    # Users who signed in within the last N days / not within the last N days.
    active_days: int | None = Field(default=None, ge=1, le=365)
    inactive_days: int | None = Field(default=None, ge=1, le=365)
    # Drivers with a pending monthly fee.
    fee_pending: bool = False
    # Accounts created in the last N days without a completed ride yet.
    new_without_ride_days: int | None = Field(default=None, ge=1, le=365)
    # Users whose phone runs an app version lower than this ("1.4.0").
    app_version_below: str | None = Field(default=None, pattern=r"^\d+(\.\d+){0,2}$", max_length=16)
    locale: Literal["es", "en"] | None = None


class CampaignBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    segment: Segment = Field(default_factory=Segment)
    channels: list[CampaignChannel] = Field(default_factory=lambda: ["push", "inbox"])
    title_es: str = Field(min_length=1, max_length=120)
    body_es: str = Field(default="", max_length=1000)
    title_en: str | None = Field(default=None, max_length=120)
    body_en: str | None = Field(default=None, max_length=1000)
    # An app screen ("/wallet", "/profile/invite") or an https link.
    deep_link: str | None = Field(default=None, max_length=300, pattern=r"^(/|https://)\S*$")
    scheduled_at: datetime | None = None

    @field_validator("channels")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        value = list(dict.fromkeys(value))
        if not value:
            raise ValueError("Pick at least one channel")
        return value


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    segment: Segment | None = None
    channels: list[CampaignChannel] | None = None
    title_es: str | None = Field(default=None, min_length=1, max_length=120)
    body_es: str | None = Field(default=None, max_length=1000)
    title_en: str | None = Field(default=None, max_length=120)
    body_en: str | None = Field(default=None, max_length=1000)
    deep_link: str | None = Field(default=None, max_length=300, pattern=r"^(/|https://)\S*$")
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def _channels(self) -> Self:
        if self.channels is not None:
            self.channels = list(dict.fromkeys(self.channels))
            if not self.channels:
                raise ValueError("Pick at least one channel")
        return self


class CampaignStats(BaseModel):
    """targeted = frozen audience; sent = got it on some channel; skipped by reason;
    pushed = phones it was pushed to; delivered = Expo receipts ok; opened = read or tapped."""

    targeted: int = 0
    pending: int = 0
    sent: int = 0
    skipped: int = 0
    skipped_opt_out: int = 0
    skipped_cap: int = 0
    skipped_no_channel: int = 0
    pushed: int = 0
    delivered: int = 0
    emailed: int = 0
    opened: int = 0


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: CampaignStatus
    segment: Segment
    channels: list[str]
    title_es: str
    body_es: str
    title_en: str | None
    body_en: str | None
    deep_link: str | None
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    stats: CampaignStats
    created_by_id: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AudienceCount(BaseModel):
    total: int
    with_push: int  # users with an active phone
    passengers: int
    drivers: int


class CampaignSchedule(BaseModel):
    """Send now (no date) or at ``scheduled_at``. Marketing still waits for each user's quiet
    hours to end."""

    scheduled_at: datetime | None = None


# --- Email templates (doc 14) -------------------------------------------------------------------


class EmailTemplateInfo(BaseModel):
    name: str
    label: str
    description: str


class EmailPreview(BaseModel):
    name: str
    locale: str
    subject: str
    html: str
    text: str
