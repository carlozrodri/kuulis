"""Password hashing (Argon2) and JWT helpers."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from kuulis.core.exceptions import AuthenticationError
from kuulis.settings import settings

TokenType = Literal["access", "refresh", "password_reset", "email_verification"]

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> tuple[bool, str | None]:
    """Returns (is_valid, new_hash_if_rehash_needed)."""
    return password_hasher.verify_and_update(password, hashed)


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
