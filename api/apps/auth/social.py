"""Google and Apple ID token verification against the providers' public keys (JWKS).

The mobile app signs in with the native SDK and sends us the provider's ``id_token``. We check the
signature with the provider's JWKS (cached in Redis), plus ``iss``, ``aud`` and ``exp``.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import jwt

from kuulis.core.cache import cache_delete, cache_get, cache_set
from kuulis.core.exceptions import AppError, AuthenticationError, ServiceUnavailableError
from kuulis.settings import settings

logger = logging.getLogger(__name__)

Provider = Literal["google", "apple"]

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUERS = ("https://appleid.apple.com",)

JWKS_URLS: dict[Provider, str] = {"google": GOOGLE_JWKS_URL, "apple": APPLE_JWKS_URL}
JWKS_TTL_SECONDS = 6 * 3600  # Both providers rotate keys rarely and overlap old/new keys.
CLOCK_LEEWAY_SECONDS = 60


@dataclass(frozen=True)
class SocialIdentity:
    provider: Provider
    subject: str
    email: str | None
    email_verified: bool
    name: str | None = None


def _invalid(message: str = "Invalid social token") -> AuthenticationError:
    return AuthenticationError(message, code="social_token_invalid")


def _client_ids(provider: Provider) -> list[str]:
    ids = settings.GOOGLE_CLIENT_IDS if provider == "google" else settings.APPLE_CLIENT_IDS
    if not ids:
        raise AppError(f"{provider.title()} sign-in is disabled", code="social_provider_disabled")
    return ids


async def fetch_jwks(provider: Provider) -> dict[str, Any]:
    """Downloads the provider's JWKS. Tests replace this function (no network)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(JWKS_URLS[provider])
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Could not fetch %s JWKS: %s", provider, exc)
        raise ServiceUnavailableError(
            "Sign-in provider unavailable", code="social_provider_unavailable"
        ) from exc


async def _jwks(provider: Provider, *, refresh: bool = False) -> dict[str, Any]:
    cache_key = f"auth:jwks:{provider}"
    if refresh:
        await cache_delete(cache_key)
    else:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
    jwks = await fetch_jwks(provider)
    await cache_set(cache_key, jwks, ttl=JWKS_TTL_SECONDS)
    return jwks


def _find_key(jwks: dict[str, Any], kid: str) -> jwt.PyJWK | None:
    for data in jwks.get("keys", []):
        if data.get("kid") == kid:
            try:
                return jwt.PyJWK(data)
            except jwt.PyJWTError:
                return None
    return None


async def _signing_key(provider: Provider, token: str) -> jwt.PyJWK:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _invalid() from exc
    kid = header.get("kid")
    if header.get("alg") != "RS256" or not kid:
        raise _invalid()
    key = _find_key(await _jwks(provider), kid)
    if key is None:
        # Keys rotated since we cached them: refetch once.
        key = _find_key(await _jwks(provider, refresh=True), kid)
    if key is None:
        raise _invalid()
    return key


async def _decode(
    provider: Provider, token: str, issuers: tuple[str, ...], audience: list[str]
) -> dict[str, Any]:
    key = await _signing_key(provider, token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _invalid("Social token expired") from exc
    except jwt.PyJWTError as exc:
        raise _invalid() from exc
    if claims.get("iss") not in issuers or not claims.get("sub"):
        raise _invalid()
    return claims


def _as_bool(value: Any) -> bool:
    # Apple sends "true"/"false" strings; Google sends booleans.
    return value is True or (isinstance(value, str) and value.lower() == "true")


async def verify_google_token(token: str) -> SocialIdentity:
    audience = _client_ids("google")
    claims = await _decode("google", token, GOOGLE_ISSUERS, audience)
    if not claims.get("email") or not _as_bool(claims.get("email_verified")):
        raise _invalid("Google email is not verified")
    return SocialIdentity(
        provider="google",
        subject=str(claims["sub"]),
        email=claims["email"],
        email_verified=True,
        name=claims.get("name"),
    )


async def verify_apple_token(token: str) -> SocialIdentity:
    audience = _client_ids("apple")
    claims = await _decode("apple", token, APPLE_ISSUERS, audience)
    email = claims.get("email")
    return SocialIdentity(
        provider="apple",
        subject=str(claims["sub"]),
        email=email,
        # Apple only issues verified addresses (real or private relay), but trust the claim.
        email_verified=bool(email) and _as_bool(claims.get("email_verified", "true")),
    )
