"""Staff roles and permissions (doc 06)."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth import services as auth_services
from apps.auth.models import UserTotp
from apps.staff.models import StaffRole
from apps.staff.permissions import ALL_PERMISSIONS
from apps.staff.schemas import (
    StaffInvite,
    StaffMember,
    StaffRoleCreate,
    StaffRoleUpdate,
    StaffUpdate,
)
from apps.users import services as users
from apps.users.models import Role, User
from apps.users.tasks import send_templated_email
from kuulis.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from kuulis.core.security import create_token, decode_token
from kuulis.settings import settings

INVITE_TTL = timedelta(days=3)


async def permissions_of(session: AsyncSession, user: User) -> frozenset[str]:
    """What ``user`` may do in the admin; computed once per request."""
    cached = getattr(user, "_permissions", None)
    if cached is not None:
        return cached
    granted: frozenset[str] = frozenset()
    if user.role == Role.ADMIN:
        granted = ALL_PERMISSIONS
    elif user.role == Role.STAFF and user.staff_role_id is not None:
        stored = await session.scalar(
            select(StaffRole.permissions).where(StaffRole.id == user.staff_role_id)
        )
        granted = frozenset(stored or ()) & ALL_PERMISSIONS
    user._permissions = granted  # type: ignore[attr-defined]
    return granted


async def list_roles(session: AsyncSession) -> list[StaffRole]:
    return list(await session.scalars(select(StaffRole).order_by(StaffRole.label)))


async def get_role(session: AsyncSession, role_id: uuid.UUID) -> StaffRole:
    role = await session.get(StaffRole, role_id)
    if role is None:
        raise NotFoundError("Staff role not found", code="staff_role_not_found")
    return role


# --- Roles --------------------------------------------------------------------------------------


async def member_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(User.staff_role_id, func.count())
        .where(User.role == Role.STAFF, User.staff_role_id.is_not(None))
        .group_by(User.staff_role_id)
    )
    return {role_id: count for role_id, count in rows.all()}


async def create_role(session: AsyncSession, data: StaffRoleCreate) -> StaffRole:
    if await session.scalar(select(StaffRole.id).where(StaffRole.name == data.name)):
        raise ConflictError("A role with that name exists", code="staff_role_exists")
    role = StaffRole(name=data.name, label=data.label, permissions=data.permissions)
    session.add(role)
    await session.flush()
    return role


async def update_role(session: AsyncSession, role: StaffRole, data: StaffRoleUpdate) -> StaffRole:
    if data.label is not None:
        role.label = data.label
    if data.permissions is not None:
        role.permissions = data.permissions
    await session.flush()
    return role


# --- Team ---------------------------------------------------------------------------------------


async def team(session: AsyncSession) -> list[StaffMember]:
    rows = await session.execute(
        select(User, StaffRole.label, UserTotp.confirmed_at)
        .outerjoin(StaffRole, StaffRole.id == User.staff_role_id)
        .outerjoin(UserTotp, UserTotp.user_id == User.id)
        .where(User.role.in_((Role.STAFF, Role.ADMIN)), User.deleted_at.is_(None))
        .order_by(User.is_active.desc(), User.role, User.full_name, User.email)
    )
    return [member(user, label, confirmed) for user, label, confirmed in rows.all()]


def member(user: User, role_label: str | None, totp_confirmed: datetime | None) -> StaffMember:
    return StaffMember(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        staff_role_id=user.staff_role_id,
        staff_role_label=role_label,
        is_active=user.is_active,
        totp_enabled=totp_confirmed is not None,
        invite_pending=not user.hashed_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


async def member_of(session: AsyncSession, user: User) -> StaffMember:
    label = (
        await session.scalar(select(StaffRole.label).where(StaffRole.id == user.staff_role_id))
        if user.staff_role_id
        else None
    )
    confirmed = await session.scalar(
        select(UserTotp.confirmed_at).where(UserTotp.user_id == user.id)
    )
    return member(user, label, confirmed)


async def invite(session: AsyncSession, data: StaffInvite) -> User:
    """Creates a staff account with no password and emails a one-time link to set it. Inviting
    again someone who has not accepted yet sends a new link."""
    await get_role(session, data.staff_role_id)
    user = await users.get_by_email(session, data.email)
    if user is not None and (user.role != Role.STAFF or user.hashed_password):
        raise ConflictError("That email already has an account", code="email_taken")
    if user is None:
        user = User(
            email=users.normalize_email(data.email),
            hashed_password=None,
            full_name=data.full_name,
            locale=data.locale,
            role=Role.STAFF,
            is_verified=True,
        )
        session.add(user)
    user.full_name = data.full_name
    user.staff_role_id = data.staff_role_id
    await session.flush()
    token, _, _ = create_token(str(user.id), "staff_invite", INVITE_TTL)
    link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
    await send_templated_email.kiq(user.email, "invite", user.locale, user.full_name, link)
    return user


async def accept_invite(session: AsyncSession, token: str, password: str) -> None:
    payload = decode_token(token, "staff_invite")
    user = await users.get_by_id(session, uuid.UUID(payload["sub"]))
    if user is None or user.role != Role.STAFF or user.hashed_password or not user.is_active:
        raise AuthenticationError("Invitation no longer valid", code="invite_invalid")
    await auth_services.consume_one_time_token(token, "staff_invite")
    await users.set_password(user, password)


async def update_member(session: AsyncSession, actor: User, user: User, data: StaffUpdate) -> User:
    if not user.can_access_admin:
        raise NotFoundError("Team member not found", code="staff_not_found")
    changes = data.model_dump(exclude_unset=True)
    if user.id == actor.id and (
        changes.get("role", Role.ADMIN) != Role.ADMIN or changes.get("is_active") is False
    ):
        raise PermissionDeniedError("You cannot demote or disable yourself", code="self_demotion")
    if changes.get("staff_role_id") is not None:
        await get_role(session, changes["staff_role_id"])
    for field, value in changes.items():
        setattr(user, field, value)
    await session.flush()
    if changes.get("is_active") is False or "role" in changes or "staff_role_id" in changes:
        await auth_services.revoke_all(str(user.id))  # new powers apply from the next sign-in
    return user
