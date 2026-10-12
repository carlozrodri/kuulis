"""Password hashing (Argon2) and JWT helpers."""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from kuulis.core.exceptions import AuthenticationError
from kuulis.settings import settings

TokenType = Literal["access", "refresh", "password_reset", "email_verification", "staff_invite"]

# Argon2id with OWASP's first recommended configuration (19 MiB, 2 passes, 1 lane). pwdlib's default
# (64 MiB, 3 passes, 4 lanes) costs ~230 ms of CPU per login against ~30 ms: in the doc 18 load test
# the 8-thread QA server topped out at ~22 logins/s. Older hashes still verify and are upgraded on
# the next login (verify_and_update).
password_hasher = PasswordHash((Argon2Hasher(time_cost=2, memory_cost=19456, parallelism=1),))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Returns (is_valid, new_hash_if_rehash_needed)."""
    return password_hasher.verify_and_update(password, hashed)


# Argon2 takes ~30 ms of CPU and 19 MB on purpose. Run on the event loop it would freeze every
# other request of the process meanwhile (doc 18 load test); a small pool keeps it off the loop
# and caps the memory used by logins arriving together.
_hash_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="argon2")


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(_hash_pool, hash_password, password)


async def verify_password_async(password: str, hashed: str) -> tuple[bool, str | None]:
    return await asyncio.get_running_loop().run_in_executor(
        _hash_pool, verify_password, password, hashed
    )


def create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    """Returns (encoded_token, jti, expires_at)."""
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
        "iss": settings.APP_NAME.lower(),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME.lower(),
            options={"require": ["exp", "sub", "type", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token", code="token_invalid") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type", code="token_invalid")
    return payload
