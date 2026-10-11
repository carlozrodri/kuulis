"""Auth dependencies: current user and role-based permissions."""

import uuid
from typing import Annotated

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


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AuthenticationError()
    user = await user_from_token(session, credentials.credentials)
    set_log_field("user_id", user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    async def _checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        if user.can_access_admin and not has_admin_session(user):
            # A staff account signed in from the app (password only): no admin powers there.
            raise PermissionDeniedError("Sign in to the admin panel", code="admin_mfa_required")
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
