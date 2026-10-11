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
    is_test_account: bool = False
    created_at: datetime
    last_login_at: datetime | None
    # Rating received as a passenger.
    rating_avg: float | None = None
    rating_count: int = 0
    trusted_contact_name: str | None = None
    trusted_contact_phone: str | None = None
    suspension: SuspensionRead | None = None
    # Admin panel accounts only (/users/me): what their role lets them do (apps.staff).
    permissions: list[str] | None = None
    # Legal texts (doc 07) this user still has to accept; only on their own account.
    pending_legal: list[str] | None = None
    # Explicit permissions in force (apps.privacy); only on their own account.
    consents: list[str] | None = None
    # Account deletion: asked for (inactive, restorable by signing in until erase) and carried out.
    deletion_requested_at: datetime | None = None
    deleted_at: datetime | None = None


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
    # Both null (or "") remove the contact. The phone is E.164 ("+584121234567").
    trusted_contact_name: str | None = Field(default=None, max_length=80)
    trusted_contact_phone: str | None = Field(default=None, pattern=r"^(\+\d{10,15})?$")


class DeletionScheduled(BaseModel):
    """DELETE /users/me: the personal data is erased at ``erase_at`` unless the user signs in."""

    erase_at: datetime


class UserAdminCreate(UserCreate):
    role: Role = Role.USER
    is_verified: bool = True


class UserAdminUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=150)
    role: Role | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    is_test_account: bool | None = None
    locale: Locale | None = None


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserStats(BaseModel):
    total: int
    active: int
    verified: int
    by_role: dict[str, int]
