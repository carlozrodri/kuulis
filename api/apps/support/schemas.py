import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from apps.support.models import CannedAction, HelpAudience, HelpTopic, LostItemAnswer
from apps.users.schemas import UserBrief


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _text(min_length: int, max_length: int):
    return Annotated[
        str, BeforeValidator(_strip), Field(min_length=min_length, max_length=max_length)
    ]


Locale = Literal["es", "en"]
Tag = Annotated[str, BeforeValidator(_strip), Field(min_length=1, max_length=40)]


# --- Help center -------------------------------------------------------------------------------


class HelpArticleSummary(BaseModel):
    id: uuid.UUID
    slug: str
    locale: str
    topic: HelpTopic
    audience: HelpAudience
    title: str
    excerpt: str
    position: int
    updated_at: datetime


class HelpArticleRead(HelpArticleSummary):
    body_md: str


class HelpArticleAdminRead(HelpArticleRead):
    published: bool
    views: int
    helpful_yes: int
    helpful_no: int


class HelpFeedback(BaseModel):
    helpful: bool


class HelpArticleCreate(BaseModel):
    slug: Annotated[str, Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
    locale: Locale = "es"
    topic: HelpTopic
    audience: HelpAudience = HelpAudience.ALL
    title: _text(3, 200)  # type: ignore[valid-type]
    body_md: _text(1, 20_000)  # type: ignore[valid-type]
    published: bool = False
    position: int = Field(default=0, ge=0, le=10_000)


class HelpArticleUpdate(BaseModel):
    slug: (
        Annotated[str, Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
        | None
    ) = None
    locale: Locale | None = None
    topic: HelpTopic | None = None
    audience: HelpAudience | None = None
    title: _text(3, 200) | None = None  # type: ignore[valid-type]
    body_md: _text(1, 20_000) | None = None  # type: ignore[valid-type]
    published: bool | None = None
    position: int | None = Field(default=None, ge=0, le=10_000)


# --- Saved replies -----------------------------------------------------------------------------


class CannedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    locale: str
    action: CannedAction
    tags: list[str]
    uses: int
    created_at: datetime
    updated_at: datetime


class CannedCreate(BaseModel):
    title: _text(2, 120)  # type: ignore[valid-type]
    body: _text(1, 4000)  # type: ignore[valid-type]
    locale: Locale = "es"
    action: CannedAction = CannedAction.NONE
    tags: list[Tag] = Field(default_factory=list, max_length=10)


class CannedUpdate(BaseModel):
    title: _text(2, 120) | None = None  # type: ignore[valid-type]
    body: _text(1, 4000) | None = None  # type: ignore[valid-type]
    locale: Locale | None = None
    action: CannedAction | None = None
    tags: list[Tag] | None = Field(default=None, max_length=10)


class TagCount(BaseModel):
    tag: str
    count: int


# --- Lost items --------------------------------------------------------------------------------


class LostItemCreate(BaseModel):
    description: _text(3, 500)  # type: ignore[valid-type]


class LostItemAnswerCreate(BaseModel):
    has_it: bool


class LostItemRead(BaseModel):
    id: uuid.UUID
    ride_id: uuid.UUID
    description: str
    answer: LostItemAnswer | None
    answered_at: datetime | None
    chat_until: datetime | None
    chat_open: bool
    report_id: uuid.UUID | None
    created_at: datetime


# --- Public contact ----------------------------------------------------------------------------


class ContactChallenge(BaseModel):
    challenge: str
    difficulty: int
    expires_in: int


class ContactCreate(BaseModel):
    name: _text(2, 120)  # type: ignore[valid-type]
    email: EmailStr
    message: _text(10, 2000)  # type: ignore[valid-type]
    category: Literal["app_issue", "other"] = "other"
    locale: Locale = "es"
    challenge: Annotated[str, Field(max_length=300)]
    nonce: Annotated[str, Field(max_length=64)]


class ContactAccepted(BaseModel):
    ok: bool = True


# --- Metrics -----------------------------------------------------------------------------------


class SupportDay(BaseModel):
    date: str
    created: int
    resolved: int


class AgentMetrics(BaseModel):
    user: UserBrief | None
    resolved: int
    first_response_minutes_avg: float | None
    csat_avg: float | None


class SupportMetrics(BaseModel):
    days: list[SupportDay]
    first_response_minutes_avg: float | None
    resolution_hours_avg: float | None
    csat_avg: float | None
    csat_count: int
    overdue_open: int
    waiting_staff: int
    by_agent: list[AgentMetrics]
