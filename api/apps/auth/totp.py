"""Second factor for the admin panel: TOTP (Google Authenticator, Aegis…) plus single-use
recovery codes. Required for every staff/admin account (``ADMIN_TOTP_REQUIRED``).

Login: the password step answers with a short-lived challenge; the code step turns it into
tokens whose session is marked ``mfa`` (only those reach the staff endpoints). Sensitive actions
also ask for a fresh code (``reauth``), valid for REAUTH_SECONDS on that session.
"""

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import UTC, datetime

import pyotp
import segno
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth.models import UserTotp
from apps.auth.schemas import AdminLoginStep, TotpSetup
from apps.users import services as users
from apps.users.models import User
from kuulis.core import crypto
from kuulis.core.exceptions import AppError, AuthenticationError
from kuulis.core.redis import redis_client
from kuulis.settings import settings

CHALLENGE_SECONDS = 5 * 60
MAX_ATTEMPTS = 5
REAUTH_SECONDS = 10 * 60
RECOVERY_CODES = 10
_PREFIX = f"{settings.APP_ENV}:auth:totp"


def _challenge_key(challenge: str) -> str:
    return f"{_PREFIX}:challenge:{challenge}"


def _reauth_key(sid: str) -> str:
    return f"{_PREFIX}:reauth:{sid}"


def _issuer() -> str:
    return "Kuulis" if settings.APP_ENV == "production" else f"Kuulis {settings.APP_ENV.upper()}"


def _hash(code: str) -> str:
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def _normalize(code: str) -> str:
    return code.replace("-", "").replace(" ", "").strip().lower()


def _new_recovery_codes() -> list[str]:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def _matching_step(secret: str, code: str, after_step: int) -> int | None:
    """The time step whose code matches (current one or its neighbours, for clock drift), if it
    is newer than ``after_step`` (a code is accepted only once)."""
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(time.time()) // totp.interval
    for step in (now_step - 1, now_step, now_step + 1):
        if step > after_step and hmac.compare_digest(totp.at(step * totp.interval), code):
            return step
    return None


async def get(session: AsyncSession, user_id: uuid.UUID) -> UserTotp | None:
    return await session.scalar(select(UserTotp).where(UserTotp.user_id == user_id))


async def check_code(session: AsyncSession, user: User, code: str) -> None:
    """A code from the app or an unused recovery code; raises ``totp_invalid``."""
    totp = await get(session, user.id)
    if totp is None or totp.confirmed_at is None:
        raise AppError("Second factor not set up", code="totp_invalid")
    step = _matching_step(crypto.decrypt(totp.secret), code, totp.last_step)
    if step is not None:
        totp.last_step = step
        return
    hashed = _hash(code)
    if hashed in totp.recovery_codes:
        totp.recovery_codes = [c for c in totp.recovery_codes if c != hashed]
        return
    raise AppError("Invalid code", code="totp_invalid")


async def start_admin_login(session: AsyncSession, user: User) -> AdminLoginStep:
    challenge = secrets.token_urlsafe(24)
    data = {"user_id": str(user.id)}
    totp = await get(session, user.id)
    setup = None
    if totp is None or totp.confirmed_at is None:
        secret = pyotp.random_base32()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=_issuer())
        qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2)
        setup = TotpSetup(secret=secret, otpauth_uri=uri, qr_data_uri=qr)
        data["secret"] = crypto.encrypt(secret)
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.hset(_challenge_key(challenge), mapping=data)
        pipe.expire(_challenge_key(challenge), CHALLENGE_SECONDS)
        await pipe.execute()
    status = "totp_setup" if setup else "totp_required"
    return AdminLoginStep(status=status, challenge=challenge, setup=setup)


async def complete_admin_login(
    session: AsyncSession, challenge: str, code: str
) -> tuple[User, list[str] | None]:
    """Returns the user and, right after a setup, the recovery codes to show once."""
    key = _challenge_key(challenge)
    data = await redis_client.hgetall(key)
    if not data or await redis_client.hincrby(key, "attempts", 1) > MAX_ATTEMPTS:
        await redis_client.delete(key)
        raise AppError("Sign in again", code="totp_challenge_expired")
    user = await users.get_by_id(session, uuid.UUID(data["user_id"]))
    if user is None or not user.is_active or not user.can_access_admin:
        await redis_client.delete(key)
        raise AuthenticationError("User not found or inactive", code="user_inactive")

    if "secret" not in data:
        await check_code(session, user, code)
        await redis_client.delete(key)
        return user, None

    step = _matching_step(crypto.decrypt(data["secret"]), code, 0)
    if step is None:
        raise AppError("Invalid code", code="totp_invalid")
    codes = _new_recovery_codes()
    await session.execute(delete(UserTotp).where(UserTotp.user_id == user.id))
    session.add(
        UserTotp(
            user_id=user.id,
            secret=data["secret"],
            confirmed_at=datetime.now(UTC),
            recovery_codes=[_hash(c) for c in codes],
            last_step=step,
        )
    )
    await redis_client.delete(key)
    return user, codes


async def reauthenticate(session: AsyncSession, user: User, sid: str, code: str) -> None:
    await check_code(session, user, code)
    await redis_client.set(_reauth_key(sid), "1", ex=REAUTH_SECONDS)


async def recently_verified(sid: str | None) -> bool:
    return bool(sid) and bool(await redis_client.exists(_reauth_key(sid)))


async def reset(session: AsyncSession, user: User) -> None:
    """An admin removes a staff member's authenticator (lost phone): they set it up again at their
    next sign-in. Their open sessions end."""
    from apps.auth import services as auth

    await session.execute(delete(UserTotp).where(UserTotp.user_id == user.id))
    await auth.revoke_all(str(user.id))
