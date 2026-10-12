import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.config.schemas import AppLinks, AreaPause, Localized, LocationIntervals, Maintenance

Mode = Literal["passenger", "driver"]
Platform = Literal["android", "ios", "web"]
Style = Literal["info", "warning", "promo"]
# Screens a banner button can open in the app.
Screen = Literal["home", "wallet", "promotions", "profile", "about", "driver_signup"]


# --- App status ----------------------------------------------------------------------------------


class AppStatus(BaseModel):
    maintenance: Maintenance
    area_pauses: list[AreaPause] = Field(max_length=20)


class AppStatusRead(AppStatus):
    areas: list[str]  # service area names, for the admin pickers


class Notice(BaseModel):
    """Why new rides are stopped: maintenance (global or one city) or a city pause."""

    kind: Literal["maintenance", "pause"]
    area: str | None
    message: Localized
    eta: datetime | None


# --- Feature flags -------------------------------------------------------------------------------


class FlagRules(BaseModel):
    """Who gets a flag that is on. An empty list (or null) does not narrow anything."""

    platforms: list[Platform] = Field(default_factory=list)
    min_build: int | None = Field(default=None, ge=0)
    areas: list[str] = Field(default_factory=list, max_length=20)
    roles: list[Mode] = Field(default_factory=list)
    percent: int = Field(default=100, ge=0, le=100)


class FlagUpdate(BaseModel):
    enabled: bool
    rules: FlagRules = Field(default_factory=FlagRules)


class FlagRead(BaseModel):
    key: str
    description: str
    default: bool
    enabled: bool
    rules: FlagRules
    changed: bool  # false while it still follows the default
    updated_at: datetime | None = None
    updated_by_email: str | None = None


class FlagCheck(BaseModel):
    """Whether one account gets the flag (the admin's preview)."""

    email: str
    role: Mode
    enabled: bool


# --- Announcements -------------------------------------------------------------------------------


class Target(BaseModel):
    roles: list[Mode] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list, max_length=20)


class Cta(BaseModel):
    label: Localized
    url: str | None = Field(default=None, max_length=500, pattern=r"^https://")
    screen: Screen | None = None

    @model_validator(mode="after")
    def _one_destination(self) -> Self:
        if (self.url is None) == (self.screen is None):
            raise ValueError("give either url or screen")
        return self


class AnnouncementBase(BaseModel):
    title: Localized
    body: Localized
    target: Target = Field(default_factory=Target)
    cta: Cta | None = None
    starts_at: datetime
    ends_at: datetime
    dismissible: bool = True
    style: Style = "info"

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if not self.title.es.strip():
            raise ValueError("title.es is required")
        return self


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(AnnouncementBase):
    pass


class AnnouncementRead(AnnouncementBase):
    """What the app gets."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class AnnouncementAdminRead(AnnouncementRead):
    created_at: datetime
    created_by_email: str | None = None
    seen: int = 0  # accounts or devices that got it
    dismissed: int = 0


# --- Bootstrap -----------------------------------------------------------------------------------


class Bootstrap(BaseModel):
    """Everything the app reads at start and every few minutes (``GET /app/bootstrap``)."""

    area: str | None  # service area at lat/lng (null: unknown or outside every city)
    maintenance: Notice | None  # global maintenance: the app shows its maintenance screen
    paused_areas: list[Notice]  # cities where new rides are stopped (maintenance or pause)
    service: Notice | None  # what applies at lat/lng (global maintenance or this city's notice)
    flags: dict[str, bool]
    announcements: list[AnnouncementRead]
    links: AppLinks
    location_intervals: LocationIntervals
    min_build: int
    refresh_seconds: int
