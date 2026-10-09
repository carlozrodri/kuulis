"""JWT access tokens + rotating refresh tokens stored in Redis (revocable)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth.schemas import TokenPair
from apps.auth.social import SocialIdentity
from apps.users import services as users
from apps.users.models import SocialAccount, User
from apps.users.tasks import send_templated_email
from kuulis.core.exceptions import AuthenticationError
from kuulis.core.redis import redis_client
from kuulis.core.security import create_token, decode_token
from kuulis.settings import settings

_PREFIX = f"{settings.APP_ENV}:auth"


def _refresh_key(jti: str) -> str:
    return f"{_PREFIX}:refresh:{jti}"


def _user_sessions_key(user_id: str) -> str:
    return f"{_PREFIX}:sessions:{user_id}"


def _used_token_key(jti: str) -> str:
    return f"{_PREFIX}:used:{jti}"


async def issue_tokens(user: User) -> TokenPair:
    user_id = str(user.id)
    access, _, _ = create_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
        extra={"role": user.role.value},
    )
    refresh_ttl = timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    refresh, jti, _ = create_token(user_id, "refresh", refresh_ttl)
    seconds = int(refresh_ttl.total_seconds())
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(_refresh_key(jti), user_id, ex=seconds)
        pipe.sadd(_user_sessions_key(user_id), jti)
        pipe.expire(_user_sessions_key(user_id), seconds)
        await pipe.execute()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
    )


async def rotate_refresh_token(session: AsyncSession, refresh_token: str) -> tuple[User, TokenPair]:
    payload = decode_token(refresh_token, "refresh")
    jti, user_id = payload["jti"], payload["sub"]
    # GETDEL makes the token single use even with concurrent requests.
    stored = await redis_client.getdel(_refresh_key(jti))
    if stored != user_id:
        # Reuse of a rotated token: revoke every session of that user.
        await revoke_all(user_id)
        raise AuthenticationError("Refresh token revoked", code="token_revoked")
    await redis_client.srem(_user_sessions_key(user_id), jti)
    user = await users.get_by_id(session, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    return user, await issue_tokens(user)


async def revoke(refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except AuthenticationError:
        return
    await redis_client.delete(_refresh_key(payload["jti"]))
    await redis_client.srem(_user_sessions_key(payload["sub"]), payload["jti"])


async def revoke_all(user_id: str) -> None:
    jtis = await redis_client.smembers(_user_sessions_key(user_id))
    keys = [_refresh_key(j) for j in jtis] + [_user_sessions_key(user_id)]
    await redis_client.delete(*keys)


async def _consume_one_time_token(token: str, token_type) -> dict:
    payload = decode_token(token, token_type)
    ttl = max(int(payload["exp"] - payload["iat"]), 1)
    first_use = await redis_client.set(_used_token_key(payload["jti"]), "1", ex=ttl, nx=True)
    if not first_use:
        raise AuthenticationError("Token already used", code="token_used")
    return payload


async def send_verification_email(user: User) -> None:
    token, _, _ = create_token(
        str(user.id),
        "email_verification",
        timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
    )
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    await send_templated_email.kiq(user.email, "verify", user.locale, user.full_name, link)


async def verify_email(session: AsyncSession, token: str) -> User:
    payload = await _consume_one_time_token(token, "email_verification")
    user = await users.get_or_404(session, uuid.UUID(payload["sub"]))
    user.is_verified = True
    return user


async def request_password_reset(session: AsyncSession, email: str) -> None:
    user = await users.get_by_email(session, email)
    if user is None or not user.is_active:
        return  # Never reveal whether an email exists.
    token, _, _ = create_token(
        str(user.id), "password_reset", timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)
    )
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    await send_templated_email.kiq(user.email, "reset", user.locale, user.full_name, link)


async def confirm_password_reset(session: AsyncSession, token: str, new_password: str) -> None:
    payload = await _consume_one_time_token(token, "password_reset")
    user = await users.get_or_404(session, uuid.UUID(payload["sub"]))
    await users.set_password(user, new_password)
    await revoke_all(str(user.id))


async def social_login(
    session: AsyncSession, identity: SocialIdentity, full_name: str | None = None
) -> User:
    """Finds the user by social account, then by verified email (linking it), else creates one."""
    account = await session.scalar(
        select(SocialAccount).where(
            SocialAccount.provider == identity.provider,
            SocialAccount.provider_user_id == identity.subject,
        )
    )
    user: User | None = None
    if account is not None:
        user = await users.get_by_id(session, account.user_id)
        if identity.email:
            account.email = identity.email
    if user is None:
        if not identity.email or not identity.email_verified:
            # Apple omits the email after the first sign-in; without it we cannot link or create.
            raise AuthenticationError(
                "Social token has no verified email", code="social_token_invalid"
            )
        user = await users.get_by_email(session, identity.email)
        if user is None:
            user = User(
                email=users.normalize_email(identity.email),
                hashed_password=None,
                full_name=(full_name or identity.name or "").strip()[:150],
                is_verified=True,
            )
            session.add(user)
            await session.flush()
        elif not user.is_verified:
            # Someone registered this email with a password but never proved they own it: the
            # provider just did. Drop that password so a squatter cannot keep access.
            user.hashed_password = None
            user.is_verified = True
            await revoke_all(str(user.id))
        session.add(
            SocialAccount(
                user_id=user.id,
                provider=identity.provider,
                provider_user_id=identity.subject,
                email=identity.email,
            )
        )
    if not user.is_active:
        raise AuthenticationError("Account disabled", code="user_inactive")
    if full_name and not user.full_name:
        user.full_name = full_name.strip()[:150]
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user
