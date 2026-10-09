"""Auth dependencies: current user and role-based permissions."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from apps.users import services
from apps.users.models import Role, User
from kuulis.core.db import get_db
from kuulis.core.exceptions import AuthenticationError, PermissionDeniedError
from kuulis.core.security import decode_token

bearer = HTTPBearer(auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db)]


async def user_from_token(session: AsyncSession, token: str) -> User:
    payload = decode_token(token, "access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthenticationError("Invalid token", code="token_invalid") from exc
    user = await services.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    return user


async def get_current_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AuthenticationError()
    return await user_from_token(session, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    async def _checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user

    return _checker


StaffUser = Annotated[User, Depends(require_roles(Role.STAFF, Role.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
