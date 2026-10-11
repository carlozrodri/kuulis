import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["qa", "beta", "production"]
Platform = Literal["android"]


class ReleaseRead(BaseModel):
    """What the app and the website need to offer an APK."""

    model_config = ConfigDict(from_attributes=True)

    version: str
    build: int
    size: int
    sha256: str
    md5: str
    notes: str | None
    is_mandatory: bool
    created_at: datetime
    download_url: str | None = None


class VersionCheck(BaseModel):
    """Answer to "is there a newer APK for my build?"."""

    latest: ReleaseRead | None
    minimum_build: int
    update_available: bool
    update_required: bool


class AdminReleaseRead(ReleaseRead):
    id: uuid.UUID
    platform: str
    channel: str
    file_key: str
    withdrawn_at: datetime | None
    published_by_email: str | None = None


class BuildRead(BaseModel):
    """An APK the compiler uploaded (its metadata file in S3)."""

    key: str
    file_name: str
    version: str
    build: int
    size: int
    sha256: str
    md5: str
    profile: str | None = None
    commit: str | None = None
    built_at: datetime | None = None
    published_channels: list[str] = []


class ReleaseCreate(BaseModel):
    build_key: str = Field(max_length=512)
    channel: Channel
    notes: str | None = Field(default=None, max_length=2000)
    is_mandatory: bool = False


class ReleaseUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    is_mandatory: bool | None = None
    withdrawn: bool | None = None


class VersionUsage(BaseModel):
    platform: str
    build: int
    users: int
