import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from apps.users.models import Role

Locale = Literal["es", "en"]


class UserBrief(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class SuspensionRead(BaseModel):
    """An account suspension in force (see apps.moderation)."""

    reason: str
    suspended_at: datetime
    until: datetime | None
    by: UserBrief | None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    locale: str
    avatar_key: str | None
    # Presigned GET of the profile photo (expires; re-read /users/me for a fresh one).
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None
    # Rating received as a passenger.
    rating_avg: float | None = None
    rating_count: int = 0
    suspension: SuspensionRead | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=150)
    locale: Locale = "es"


class UserUpdateMe(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    locale: Locale | None = None
    # A key from POST /files/presign-upload with folder "avatars"; null or "" removes the photo.
    avatar_key: str | None = Field(default=None, max_length=512)


class UserAdminCreate(UserCreate):
    role: Role = Role.USER
    is_verified: bool = True


class UserAdminUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    role: Role | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    locale: Locale | None = None


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserStats(BaseModel):
    total: int
    active: int
    verified: int
    by_role: dict[str, int]
