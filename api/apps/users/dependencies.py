"""Auth dependencies: current user and role-based permissions."""

import uuid
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth import services as auth_services
from apps.auth import totp
from apps.users import services
from apps.users.models import Role, User
from kuulis.core.db import get_db
from kuulis.core.exceptions import AuthenticationError, PermissionDeniedError
from kuulis.core.request_context import set_log_field
from kuulis.core.security import decode_token
from kuulis.settings import settings

bearer = HTTPBearer(auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def user_from_token(session: AsyncSession, token: str) -> User:
    payload = decode_token(token, "access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthenticationError("Invalid token", code="token_invalid") from exc
    sid = payload.get("sid")
    # A session closed from the session list stops its access tokens at once.
    if sid and not await auth_services.session_is_open(sid):
        raise AuthenticationError("Session closed", code="token_revoked")
    user = await services.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    user.auth_sid = sid
    user.auth_mfa = bool(payload.get("mfa"))
    return user


def has_admin_session(user: User) -> bool:
    """Staff/admin role and, when required, a session opened with the second factor."""
    return user.can_access_admin and (user.auth_mfa or not settings.ADMIN_TOTP_REQUIRED)


def is_service_token(token: str) -> bool:
    from apps.staff.services import SERVICE_TOKEN_PREFIX

    return token.startswith(SERVICE_TOKEN_PREFIX)


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AuthenticationError()
    if is_service_token(credentials.credentials):
        # Service tokens only open the endpoints that name a permission (see require_permission).
        raise AuthenticationError(
            "Service tokens can't use this endpoint", code="service_token_not_allowed"
        )
    user = await user_from_token(session, credentials.credentials)
    set_log_field("user_id", user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_actor(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    """The signed-in user, or the staff account behind a service token (``user.auth_scopes``
    holds what the token may do). Only :func:`require_permission` and the audit log use it."""
    if credentials is None:
        raise AuthenticationError()
    if not is_service_token(credentials.credentials):
        return await get_current_user(session, credentials)
    from apps.staff.services import user_from_service_token

    user = await user_from_service_token(session, credentials.credentials)
    set_log_field("user_id", user.id)
    return user


CurrentActor = Annotated[User, Depends(get_actor)]


def _check_roles(user: User, roles: tuple[Role, ...]) -> None:
    if user.role not in roles:
        raise PermissionDeniedError()
    if user.can_access_admin and not has_admin_session(user):
        # A staff account signed in from the app (password only): no admin powers there.
        raise PermissionDeniedError("Sign in to the admin panel", code="admin_mfa_required")


def require_roles(*roles: Role):
    async def _checker(user: CurrentUser) -> User:
        _check_roles(user, roles)
        return user

    _checker.admin_roles = roles  # type: ignore[attr-defined]  # found by the audit coverage test
    return _checker


StaffUser = Annotated[User, Depends(require_roles(Role.STAFF, Role.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]


async def ensure_recently_verified(user: User) -> None:
    """Sensitive admin actions (roles, balances, second factors) ask for a fresh code; the admin
    panel asks for it and retries (``POST /auth/admin/reauth``)."""
    if settings.ADMIN_TOTP_REQUIRED and not await totp.recently_verified(user.auth_sid):
        raise PermissionDeniedError("Confirm with your authenticator code", code="reauth_required")


async def _verified_admin(user: AdminUser) -> User:
    await ensure_recently_verified(user)
    return user


VerifiedAdminUser = Annotated[User, Depends(_verified_admin)]


def require_permission(permission: str, *, verified: bool = False):
    """Staff whose role has ``permission`` (admins have all of them); ``verified`` also asks for a
    fresh second-factor code, like :data:`VerifiedAdminUser`. A service token works here too
    when it carries ``permission`` and its account's role still has it, never for ``verified``."""
    from apps.staff.permissions import ALL_PERMISSIONS
    from apps.staff.services import permissions_of

    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Unknown permission {permission!r}")

    async def _checker(user: CurrentActor, session: DBSession) -> User:
        scopes = getattr(user, "auth_scopes", None)
        if scopes is None:
            _check_roles(user, (Role.STAFF, Role.ADMIN))
        elif verified or permission not in scopes:
            raise PermissionDeniedError(
                "This service token does not allow this",
                code="service_token_forbidden",
                details={"permission": permission},
            )
        if permission not in await permissions_of(session, user):
            raise PermissionDeniedError(
                "Your role does not allow this", details={"permission": permission}
            )
        if verified:
            await ensure_recently_verified(user)
        return user

    _checker.admin_roles = (Role.STAFF, Role.ADMIN)  # type: ignore[attr-defined]
    _checker.permission = permission  # type: ignore[attr-defined]
    return _checker


def Can(permission: str, *, verified: bool = False) -> Any:
    """``admin: Can("wallet.adjust")`` in an admin endpoint's signature."""
    return Annotated[User, Depends(require_permission(permission, verified=verified))]
