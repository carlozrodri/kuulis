"""Business logic for users. Routers stay thin; everything reusable lives here."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.users.models import Role, User
from apps.users.schemas import UserAdminCreate, UserAdminUpdate, UserCreate, UserUpdateMe
from kuulis.core import storage
from kuulis.core.exceptions import AppError, AuthenticationError, ConflictError, NotFoundError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.security import hash_password, verify_password


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
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        locale=data.locale,
        role=role,
        is_verified=is_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def admin_create_user(session: AsyncSession, data: UserAdminCreate) -> User:
    return await create_user(session, data, role=data.role, is_verified=data.is_verified)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not user.hashed_password:
        # Hash anyway to keep timing similar for unknown emails.
        hash_password(password)
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")
    valid, new_hash = verify_password(password, user.hashed_password)
    if not valid:
        raise AuthenticationError("Invalid email or password", code="invalid_credentials")
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
    for field, value in changes.items():
        setattr(user, field, value)
    return user


async def change_password(user: User, current: str, new: str) -> None:
    valid, _ = verify_password(current, user.hashed_password or "")
    if not valid:
        raise AuthenticationError("Current password is incorrect", code="invalid_credentials")
    user.hashed_password = hash_password(new)


async def set_password(user: User, new: str) -> None:
    user.hashed_password = hash_password(new)


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
