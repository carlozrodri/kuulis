import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from apps.staff.permissions import ALL_PERMISSIONS
from apps.users.models import Role


def _known(value: list[str]) -> list[str]:
    unknown = sorted(set(value) - ALL_PERMISSIONS)
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
    return sorted(set(value))


class StaffRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    label: str
    permissions: list[str]
    members: int = 0


class PermissionGroup(BaseModel):
    group: str
    permissions: list[str]


class RolesOverview(BaseModel):
    catalog: list[PermissionGroup]
    roles: list[StaffRoleRead]


class StaffRoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=80)
    permissions: list[str] = Field(default_factory=list, max_length=100)

    _check = field_validator("permissions")(_known)


class StaffRoleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=80)
    permissions: list[str] | None = Field(default=None, max_length=100)

    @field_validator("permissions")
    @classmethod
    def _perms(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _known(value)


class StaffMember(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    staff_role_id: uuid.UUID | None
    staff_role_label: str | None
    is_active: bool
    totp_enabled: bool
    invite_pending: bool  # has not set a password yet
    last_login_at: datetime | None
    created_at: datetime


class StaffInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    staff_role_id: uuid.UUID
    locale: Literal["es", "en"] = "es"


class StaffUpdate(BaseModel):
    staff_role_id: uuid.UUID | None = None
    role: Literal[Role.STAFF, Role.ADMIN] | None = None
    is_active: bool | None = None


class ServiceTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    user_id: uuid.UUID
    permissions: list[str] = Field(min_length=1, max_length=100)
    expires_at: datetime | None = None

    _check = field_validator("permissions")(_known)

    @field_validator("expires_at")
    @classmethod
    def _future(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at needs a time zone")
        if value is not None and value <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return value


class ServiceTokenRead(BaseModel):
    id: uuid.UUID
    name: str
    user_id: uuid.UUID
    user_email: str
    user_name: str
    prefix: str  # the first characters of the key, to recognise it
    permissions: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ServiceTokenCreated(ServiceTokenRead):
    token: str  # the whole key: shown only in this response


class InviteAccept(BaseModel):
    token: str = Field(max_length=2048)
    password: str = Field(max_length=128)
