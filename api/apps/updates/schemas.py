import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.releases.schemas import Channel


class CandidateAsset(BaseModel):
    """One file of an exported update, as the compiler describes it."""

    s3_key: str
    hash: str  # base64url SHA-256 (what the app checks)
    key: str  # MD5 hex: the name the bundle uses for it
    contentType: str
    fileExtension: str | None = None


class UpdateCandidate(BaseModel):
    """An exported update the compiler uploaded (``updates/<env>/candidates/*.json``)."""

    key: str = ""
    platform: Literal["android"] = "android"
    runtime_version: str
    commit: str | None = None
    message: str | None = None
    built_at: datetime | None = None
    bundle_size: int | None = None
    launch_asset: CandidateAsset
    assets: list[CandidateAsset] = []
    extra: dict = {}
    published_channels: list[str] = []


class CandidateRead(BaseModel):
    """What the admin lists (without the asset lists)."""

    key: str
    platform: str
    runtime_version: str
    commit: str | None
    message: str | None
    built_at: datetime | None
    bundle_size: int | None
    asset_count: int
    published_channels: list[str]


class UpdatePublish(BaseModel):
    candidate_key: str = Field(max_length=512)
    channel: Channel
    rollout_percent: int = Field(default=100, ge=0, le=100)
    message: str | None = Field(default=None, max_length=500)


class UpdatePatch(BaseModel):
    rollout_percent: int | None = Field(default=None, ge=0, le=100)
    message: str | None = Field(default=None, max_length=500)


class AdminUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    channel: str
    runtime_version: str
    kind: str
    commit: str | None
    message: str | None
    rollout_percent: int
    reverted_from_id: uuid.UUID | None
    created_at: datetime
    withdrawn_at: datetime | None
    published_by_email: str | None = None


class UpdateUsage(BaseModel):
    update_id: str
    users: int
