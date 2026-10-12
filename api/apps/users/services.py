"""Business logic for users. Routers stay thin; everything reusable lives here."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import ColumnElement, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.files import metadata
from apps.users import passwords
from apps.users.models import Role, SocialAccount, User
from apps.users.schemas import UserAdminCreate, UserAdminUpdate, UserCreate, UserUpdateMe
from kuulis.core import storage
from kuulis.core.exceptions import AppError, AuthenticationError, ConflictError, NotFoundError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.security import hash_password_async, verify_password_async
from kuulis.settings import settings


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == normalize_email(email)))


async def get_or_404(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    return user


async def create_user(
    session: AsyncSession,
    data: UserCreate,
    *,
    role: Role = Role.USER,
    is_verified: bool = False,
) -> User:
    email = normalize_email(data.email)
    if await get_by_email(session, email):
        raise ConflictError("Email already registered", code="email_taken")
    user = User(
        email=email,
        hashed_password=await hash_password_async(data.password),
        full_name=data.full_name,
        locale=data.locale,
        role=role,
        is_verified=is_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def admin_create_user(session: AsyncSession, data: UserAdminCreate) -> User:
    passwords.ensure_allowed(data.password)
    return await create_user(session, data, role=data.role, is_verified=data.is_verified)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not user.hashed_password:
        # Hash anyway to keep timing similar for unknown emails.
        await hash_password_async(password)
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")
    valid, new_hash = await verify_password_async(password, user.hashed_password)
    if not valid:
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")
    restore_if_pending_deletion(user)
    if not user.is_active:
        raise AuthenticationError("Account disabled", code="account_disabled")
    if new_hash:
        user.hashed_password = new_hash
    user.last_login_at = datetime.now(UTC)
    return user


async def update_me(user: User, data: UserUpdateMe) -> User:
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes:
        changes["full_name"] = (changes["full_name"] or "").strip()
    if "avatar_key" in changes:
        key = changes["avatar_key"] or None
        # Only a photo this user uploaded to their own avatars folder.
        if key is not None and not storage.key_in_folder(key, f"avatars/{user.id}"):
            raise AppError("Invalid avatar key", code="invalid_avatar_key")
        changes["avatar_key"] = key
        if key is not None and key != user.avatar_key:
            await metadata.schedule(key)
    for field in ("trusted_contact_name", "trusted_contact_phone"):
        if field in changes:
            changes[field] = (changes[field] or "").strip() or None
    if "trusted_contact_name" in changes or "trusted_contact_phone" in changes:
        name = changes.get("trusted_contact_name", user.trusted_contact_name)
        phone = changes.get("trusted_contact_phone", user.trusted_contact_phone)
        if (name is None) != (phone is None):
            raise AppError("Name and phone go together", code="trusted_contact_incomplete")
    for field, value in changes.items():
        setattr(user, field, value)
    return user


async def change_password(user: User, current: str, new: str) -> None:
    valid, _ = await verify_password_async(current, user.hashed_password or "")
    if not valid:
        raise AuthenticationError("Current password is incorrect", code="invalid_credentials")
    passwords.ensure_allowed(new)
    user.hashed_password = await hash_password_async(new)


async def set_password(user: User, new: str) -> None:
    passwords.ensure_allowed(new)
    user.hashed_password = await hash_password_async(new)


async def admin_update_user(user: User, data: UserAdminUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    return user


async def list_users(
    session: AsyncSession,
    params: PageParams,
    *,
    search: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
    where: ColumnElement[bool] | None = None,
) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.created_at.desc())
    if where is not None:
        stmt = stmt.where(where)
    if search:
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.email).like(term), func.lower(User.full_name).like(term))
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    return await paginate(session, stmt, params)


async def stats(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count(User.id))) or 0
    active = await session.scalar(select(func.count(User.id)).where(User.is_active)) or 0
    verified = await session.scalar(select(func.count(User.id)).where(User.is_verified)) or 0
    rows = await session.execute(select(User.role, func.count(User.id)).group_by(User.role))
    by_role = {role.value: 0 for role in Role} | {str(r.value): c for r, c in rows.all()}
    return {"total": total, "active": active, "verified": verified, "by_role": by_role}


# --- Account deletion --------------------------------------------------------------------------


class ActiveRideError(ConflictError):
    code = "account_ride_active"
    message = "Finish your ride before deleting your account"


class OpenReportsError(ConflictError):
    code = "account_open_reports"
    message = "There are open reports about your account; support must close them first"


class FeePendingError(ConflictError):
    code = "account_fee_pending"
    message = "Pay your pending subscription fee before deleting your account"


def erase_at(user: User) -> datetime:
    assert user.deletion_requested_at is not None
    return user.deletion_requested_at + timedelta(days=settings.ACCOUNT_DELETION_GRACE_DAYS)


def restore_if_pending_deletion(user: User) -> bool:
    """Signing in during the grace period cancels the deletion (the password or social login
    already proved it is the owner)."""
    if (
        user.is_active
        or user.deletion_requested_at is None
        or user.deleted_at is not None
        or erase_at(user) <= datetime.now(UTC)
    ):
        return False
    user.is_active = True
    user.deletion_requested_at = None
    return True


async def request_deletion(session: AsyncSession, user: User) -> datetime:
    from apps.rides.models import ACTIVE_STATUSES, Ride

    busy = await session.scalar(
        select(Ride.id)
        .where(
            or_(Ride.passenger_id == user.id, Ride.driver_id == user.id),
            Ride.status.in_(ACTIVE_STATUSES),
        )
        .limit(1)
    )
    if busy is not None:
        raise ActiveRideError()
    await ensure_deletable(session, user)
    user.is_active = False
    user.deletion_requested_at = datetime.now(UTC)
    await session.flush()
    return erase_at(user)


async def ensure_deletable(session: AsyncSession, user: User) -> None:
    """Open reports against the user and unpaid fees must be settled first (doc 07)."""
    from apps.moderation.models import OPEN_STATUSES, Report
    from apps.subscriptions.models import Charge, ChargeStatus

    reported = await session.scalar(
        select(Report.id)
        .where(Report.reported_user_id == user.id, Report.status.in_(OPEN_STATUSES))
        .limit(1)
    )
    if reported is not None:
        raise OpenReportsError()
    owed = await session.scalar(
        select(Charge.id)
        .where(Charge.user_id == user.id, Charge.status == ChargeStatus.PENDING)
        .limit(1)
    )
    if owed is not None:
        raise FeePendingError()


async def erase_due(session: AsyncSession, now: datetime | None = None, limit: int = 50) -> int:
    """Erases the personal data of accounts whose grace period ended. Rides, payments, fees and
    reports stay (accounting and safety records) but no longer point to a person."""
    from apps.drivers.models import DriverDocument, DriverProfile, Vehicle
    from apps.moderation.models import Suspension
    from apps.notifications.models import Device, Notification
    from apps.places.models import SavedPlace
    from apps.privacy import services as privacy

    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=settings.ACCOUNT_DELETION_GRACE_DAYS)
    users = list(
        await session.scalars(
            select(User)
            .where(
                User.is_active.is_(False),
                User.deleted_at.is_(None),
                User.deletion_requested_at.is_not(None),
                User.deletion_requested_at <= cutoff,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for user in users:
        tag = user.id.hex
        keys = [user.avatar_key] if user.avatar_key else []
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == user.id)
        )
        if profile is not None:
            keys += list(
                await session.scalars(
                    select(DriverDocument.key).where(DriverDocument.driver_id == profile.id)
                )
            )
            await session.execute(
                delete(DriverDocument).where(DriverDocument.driver_id == profile.id)
            )
            await session.execute(
                update(Vehicle)
                .where(Vehicle.driver_id == profile.id)
                .values(plate=f"X{tag[:11]}", color="")
            )
            profile.national_id = f"DEL{tag[:17]}"
            profile.rif = ""
            profile.phone = ""
            profile.birth_date = date(1900, 1, 1)
            profile.rejection_reason = None
        suspended = await session.scalar(
            select(func.count(Suspension.id)).where(Suspension.user_id == user.id)
        )
        keys += await privacy.scrub(session, user, was_suspended=bool(suspended))
        for model in (SocialAccount, Device, Notification, SavedPlace):
            await session.execute(delete(model).where(model.user_id == user.id))
        user.email = f"deleted-{tag}@deleted.invalid"
        user.full_name = ""
        user.hashed_password = None
        user.avatar_key = None
        user.referral_code = None
        user.trusted_contact_name = None
        user.trusted_contact_phone = None
        user.deleted_at = now
        await session.commit()
        # After the commit: a storage hiccup leaves orphan files, never a half-erased account.
        storage.delete_objects(keys)
    return len(users)
