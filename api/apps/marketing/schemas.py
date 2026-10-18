import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

Status = Literal[
    "idea", "guion", "revisado", "producido", "aprobado", "publicado", "archivado", "descartado"
]
STATUSES: tuple[str, ...] = Status.__args__  # type: ignore[attr-defined]
Platform = Literal["tiktok", "instagram", "youtube", "whatsapp", "facebook"]
Audience = Literal["motorizado", "pasajero", "ambos"]
Production = Literal["real", "ia", "mixto"]
AssetKind = Literal["video", "imagen", "audio"]
AssetRole = Literal["original", "final", "portada", "fuente"]
LearningStatus = Literal["hipotesis", "probado", "descartado"]
SpendConcept = Literal["suscripcion", "creditos", "pauta", "otro"]
AccountStatus = Literal["pendiente", "activa", "suspendida"]
Connection = Literal["manual", "api"]

# What the person posting may upload to (doc 04: files arrive ready for each network).
CONTENT_TYPES: dict[str, AssetKind] = {
    "video/mp4": "video",
    "video/quicktime": "video",
    "image/jpeg": "imagen",
    "image/png": "imagen",
    "image/webp": "imagen",
    "audio/mpeg": "audio",
    "audio/mp4": "audio",
    "audio/wav": "audio",
}

MoneyStr = PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")
Money = Annotated[Decimal, Field(ge=0, le=100000, decimal_places=2), MoneyStr]
OptionalText = Annotated[str | None, AfterValidator(lambda v: (v or "").strip() or None)]


def _hashtags(values: list[str]) -> list[str]:
    """``#Caracas`` or ``caracas`` → ``caracas``: stored without the sign, shown with it."""
    seen: list[str] = []
    for value in values:
        tag = "".join(value.split()).lstrip("#")
        if tag and tag.lower() not in (t.lower() for t in seen):
            seen.append(tag[:60])
    return seen


Hashtags = Annotated[list[str], Field(max_length=15), AfterValidator(_hashtags)]


# --- Contents --------------------------------------------------------------------------------


class ContentFields(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    pillar: OptionalText = Field(default=None, max_length=40)
    format: OptionalText = Field(default=None, max_length=40)
    audience: Audience = "ambos"
    script: dict = Field(default_factory=dict)
    uses_character: bool = False
    production: Production = "ia"
    scheduled_for: date | None = None
    notes: OptionalText = Field(default=None, max_length=4000)
    created_by_agent: OptionalText = Field(default=None, max_length=40)


class ContentCreate(ContentFields):
    status: Literal["idea", "guion"] = "idea"


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    pillar: OptionalText = Field(default=None, max_length=40)
    format: OptionalText = Field(default=None, max_length=40)
    audience: Audience | None = None
    script: dict | None = None
    uses_character: bool | None = None
    production: Production | None = None
    scheduled_for: date | None = None
    notes: OptionalText = Field(default=None, max_length=4000)


class StatusChange(BaseModel):
    status: Status


class ChangesRequested(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class ContentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    pillar: str | None
    format: str | None
    audience: str
    status: str
    production: str
    uses_character: bool
    scheduled_for: date | None
    created_by_agent: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    platforms: list[str] = []
    next_post_at: datetime | None = None


# --- Assets ----------------------------------------------------------------------------------


class AssetCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    content_type: str
    size: int = Field(gt=0)
    role: AssetRole = "final"
    source: str = Field(min_length=1, max_length=32)
    model: OptionalText = Field(default=None, max_length=80)
    prompt: OptionalText = Field(default=None, max_length=8000)
    credits_used: Annotated[Decimal, Field(ge=0, le=100000, decimal_places=2)] | None = None
    cost_usd: Money | None = None
    rights: OptionalText = Field(default=None, max_length=2000)
    width: int | None = Field(default=None, gt=0, le=10000)
    height: int | None = Field(default=None, gt=0, le=10000)
    duration_s: float | None = Field(default=None, gt=0, le=3600)

    @field_validator("content_type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        value = value.split(";")[0].strip().lower()
        if value not in CONTENT_TYPES:
            raise ValueError(f"Unsupported content type {value!r}")
        return value


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    role: str
    source: str
    model: str | None
    prompt: str | None
    credits_used: Decimal | None
    cost_usd: Annotated[Decimal, MoneyStr] | None
    rights: str | None
    s3_key: str
    filename: str
    content_type: str
    size: int
    width: int | None
    height: int | None
    duration_s: float | None
    uploaded_at: datetime | None
    created_at: datetime
    download_url: str | None = None


class AssetUpload(BaseModel):
    asset: AssetRead
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]


# --- Variants --------------------------------------------------------------------------------


class VariantFields(BaseModel):
    account: OptionalText = Field(default=None, max_length=60)
    hook_index: int = Field(default=0, ge=0, le=20)
    title: OptionalText = Field(default=None, max_length=100)
    caption: str = Field(default="", max_length=2200)
    hashtags: Hashtags = []
    checklist: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(
        default_factory=list, max_length=10
    )
    ai_label: bool = True
    duration_s: float | None = Field(default=None, gt=0, le=3600)
    asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


class VariantCreate(VariantFields):
    platform: Platform


class VariantUpdate(BaseModel):
    account: OptionalText = Field(default=None, max_length=60)
    hook_index: int | None = Field(default=None, ge=0, le=20)
    title: OptionalText = Field(default=None, max_length=100)
    caption: str | None = Field(default=None, max_length=2200)
    hashtags: Hashtags | None = None
    checklist: list[Annotated[str, Field(min_length=1, max_length=160)]] | None = Field(
        default=None, max_length=10
    )
    ai_label: bool | None = None
    duration_s: float | None = Field(default=None, gt=0, le=3600)
    asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


class MetricFields(BaseModel):
    taken_at: datetime | None = None
    age_h: int | None = Field(default=None, ge=0, le=24 * 365)
    views: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    avg_watch_s: float | None = Field(default=None, ge=0, le=3600)
    completion_rate: float | None = Field(default=None, ge=0, le=1)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    follows: int | None = Field(default=None, ge=0)
    profile_visits: int | None = Field(default=None, ge=0)
    link_clicks: int | None = Field(default=None, ge=0)


class MetricCreate(MetricFields):
    source: Connection = "manual"


class MetricRead(MetricFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    taken_at: datetime
    age_h: int
    source: str


class PublicationCreate(BaseModel):
    url: OptionalText = Field(default=None, max_length=500)
    external_id: OptionalText = Field(default=None, max_length=120)
    published_at: datetime | None = None


class PublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    platform: str
    account: str | None
    external_id: str | None
    url: str | None
    published_at: datetime
    method: str
    metrics: list[MetricRead] = []


class VariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    account: str | None
    hook_index: int
    title: str | None
    caption: str
    hashtags: list[str]
    checklist: list[str]
    ai_label: bool
    duration_s: float | None
    asset_id: uuid.UUID | None
    cover_asset_id: uuid.UUID | None
    scheduled_at: datetime | None
    utm_url: str = ""
    publication: PublicationRead | None = None


class ContentRead(ContentSummary):
    script: dict
    notes: str | None
    review_note: str | None
    variants: list[VariantRead] = []
    assets: list[AssetRead] = []
    allowed_statuses: list[str] = []


# --- Posting package (doc 04 §4) -------------------------------------------------------------


class PostingCard(BaseModel):
    variant_id: uuid.UUID
    content_id: uuid.UUID
    code: str
    content_title: str
    platform: str
    account: str | None
    scheduled_at: datetime
    title: str | None
    caption: str
    hashtags: list[str]
    checklist: list[str]
    file_url: str | None
    file_name: str | None
    file_kind: str | None
    cover_url: str | None
    publication_id: uuid.UUID | None = None
    published_at: datetime | None = None
    published_url: str | None = None


# --- Performance -----------------------------------------------------------------------------


class PerformanceRow(BaseModel):
    publication_id: uuid.UUID
    content_id: uuid.UUID
    code: str
    title: str
    pillar: str | None
    format: str | None
    platform: str
    hook_index: int
    url: str | None
    published_at: datetime
    snapshots: int
    latest: MetricRead | None


# --- Learnings, spend, accounts --------------------------------------------------------------


class LearningCreate(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    evidence: OptionalText = Field(default=None, max_length=4000)
    status: LearningStatus = "hipotesis"
    platform: Platform | None = None
    pillar: OptionalText = Field(default=None, max_length=40)
    format: OptionalText = Field(default=None, max_length=40)


class LearningUpdate(BaseModel):
    statement: str | None = Field(default=None, min_length=1, max_length=2000)
    evidence: OptionalText = Field(default=None, max_length=4000)
    status: LearningStatus | None = None
    platform: Platform | None = None
    pillar: OptionalText = Field(default=None, max_length=40)
    format: OptionalText = Field(default=None, max_length=40)


class LearningRead(LearningCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    platform: str | None
    reviewed_at: datetime | None
    created_at: datetime


class SpendCreate(BaseModel):
    date: date
    tool: str = Field(min_length=1, max_length=40)
    concept: SpendConcept
    amount_usd: Money
    notes: OptionalText = Field(default=None, max_length=1000)


class SpendRead(SpendCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    concept: str


class SpendMonth(BaseModel):
    month: str
    total: Annotated[Decimal, MoneyStr]
    by_tool: dict[str, Annotated[Decimal, MoneyStr]]
    items: list[SpendRead]


class AccountCreate(BaseModel):
    platform: Platform
    handle: str = Field(min_length=1, max_length=60)
    url: OptionalText = Field(default=None, max_length=300)
    status: AccountStatus = "pendiente"
    connection: Connection = "manual"
    notes: OptionalText = Field(default=None, max_length=1000)


class AccountUpdate(BaseModel):
    handle: str | None = Field(default=None, min_length=1, max_length=60)
    url: OptionalText = Field(default=None, max_length=300)
    status: AccountStatus | None = None
    connection: Connection | None = None
    notes: OptionalText = Field(default=None, max_length=1000)


class AccountRead(AccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    status: str
    connection: str
