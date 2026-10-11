"""JWT access tokens + rotating refresh tokens stored in Redis (revocable)."""

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.auth import lockout
from apps.auth.schemas import SessionRead, TokenPair
from apps.auth.social import SocialIdentity
from apps.users import services as users
from apps.users.models import SocialAccount, User
from apps.users.tasks import send_templated_email
from kuulis.core.exceptions import AuthenticationError, NotFoundError
from kuulis.core.redis import redis_client
from kuulis.core.security import create_token, decode_token
from kuulis.settings import settings

_PREFIX = f"{settings.APP_ENV}:auth"


def _refresh_key(jti: str) -> str:
    return f"{_PREFIX}:refresh:{jti}"


def _user_sessions_key(user_id: str) -> str:
    return f"{_PREFIX}:sessions:{user_id}"


def _session_key(sid: str) -> str:
    return f"{_PREFIX}:session:{sid}"


def _used_token_key(jti: str) -> str:
    return f"{_PREFIX}:used:{jti}"


@dataclass(frozen=True)
class ClientInfo:
    """Where a session was opened from, shown in the session list."""

    ip: str = ""
    user_agent: str = ""
    platform: str = ""  # X-Client-Platform sent by our apps: android, ios, admin

    @classmethod
    def from_request(cls, request: Request | None) -> "ClientInfo":
        if request is None:
            return cls()
        return cls(
            ip=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", "")[:300],
            platform=request.headers.get("x-client-platform", "")[:20],
        )


async def issue_tokens(
    user: User,
    request: Request | None = None,
    *,
    mfa: bool = False,
    sid: str | None = None,
) -> TokenPair:
    """Opens a session (or continues ``sid`` on a refresh). ``mfa`` marks sessions that passed
    the admin's second factor: only those reach the staff endpoints."""
    user_id = str(user.id)
    sid = sid or uuid.uuid4().hex
    claims: dict = {"role": user.role.value, "sid": sid}
    if mfa:
        claims["mfa"] = True
    access, _, _ = create_token(
        user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES), extra=claims
    )
    refresh_ttl = timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    refresh, jti, _ = create_token(user_id, "refresh", refresh_ttl, extra={"sid": sid})
    seconds = int(refresh_ttl.total_seconds())
    client = ClientInfo.from_request(request)
    now = datetime.now(UTC).isoformat()
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(_refresh_key(jti), user_id, ex=seconds)
        pipe.sadd(_user_sessions_key(user_id), sid)
        pipe.expire(_user_sessions_key(user_id), seconds)
        pipe.hsetnx(_session_key(sid), "created_at", now)
        pipe.hset(
            _session_key(sid),
            mapping={
                "user_id": user_id,
                "jti": jti,
                "last_used_at": now,
                "mfa": "1" if mfa else "0",
                **{k: v for k, v in asdict(client).items() if v},
            },
        )
        pipe.expire(_session_key(sid), seconds)
        await pipe.execute()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
    )


async def password_login(session: AsyncSession, email: str, password: str) -> User:
    await lockout.ensure_not_locked(email)
    try:
        user = await users.authenticate(session, email, password)
    except AuthenticationError as error:
        if error.code == "invalid_credentials":
            await lockout.record_failure(email, await users.get_by_email(session, email))
        raise
    await lockout.record_success(email)
    return user


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, request: Request | None = None
) -> tuple[User, TokenPair]:
    payload = decode_token(refresh_token, "refresh")
    jti, user_id, sid = payload["jti"], payload["sub"], payload.get("sid")
    # GETDEL makes the token single use even with concurrent requests.
    stored = await redis_client.getdel(_refresh_key(jti))
    if stored != user_id:
        if sid and not await redis_client.exists(_session_key(sid)):
            # The session was closed (from the session list): only this device is out.
            raise AuthenticationError("Session closed", code="token_revoked")
        # Reuse of a rotated token: revoke every session of that user.
        await revoke_all(user_id)
        raise AuthenticationError("Refresh token revoked", code="token_revoked")
    user = await users.get_by_id(session, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="user_inactive")
    mfa = bool(sid) and await redis_client.hget(_session_key(sid), "mfa") == "1"
    if not sid:  # token from before sessions had ids
        await redis_client.srem(_user_sessions_key(user_id), jti)
    return user, await issue_tokens(user, request, mfa=mfa, sid=sid)


async def _close_sessions(user_id: str, sids: list[str]) -> None:
    jtis = [await redis_client.hget(_session_key(sid), "jti") for sid in sids]
    keys = [_refresh_key(j) for j in jtis if j] + [_session_key(sid) for sid in sids]
    # Members from before sessions had ids are refresh token ids themselves.
    keys += [_refresh_key(sid) for sid in sids]
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.delete(*keys)
        pipe.srem(_user_sessions_key(user_id), *sids)
        await pipe.execute()


async def revoke(refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except AuthenticationError:
        return
    await redis_client.delete(_refresh_key(payload["jti"]))
    await _close_sessions(payload["sub"], [payload.get("sid") or payload["jti"]])


async def revoke_all(user_id: str) -> None:
    sids = list(await redis_client.smembers(_user_sessions_key(user_id)))
    if sids:
        await _close_sessions(user_id, sids)
    await redis_client.delete(_user_sessions_key(user_id))


async def revoke_others(user_id: str, keep_sid: str | None) -> None:
    """Closes every session but ``keep_sid`` (after a password change, for instance)."""
    sids = [s for s in await redis_client.smembers(_user_sessions_key(user_id)) if s != keep_sid]
    if sids:
        await _close_sessions(user_id, sids)


async def session_is_open(sid: str) -> bool:
    return bool(await redis_client.exists(_session_key(sid)))


async def list_sessions(user_id: str, current_sid: str | None) -> list[SessionRead]:
    found = []
    for sid in await redis_client.smembers(_user_sessions_key(user_id)):
        data = await redis_client.hgetall(_session_key(sid))
        if not data:
            continue  # legacy member or expired session
        found.append(
            SessionRead(
                id=sid,
                current=sid == current_sid,
                platform=data.get("platform") or None,
                device=describe_device(data.get("user_agent", ""), data.get("platform", "")),
                ip=data.get("ip") or None,
                created_at=datetime.fromisoformat(data["created_at"]),
                last_used_at=datetime.fromisoformat(data["last_used_at"]),
                admin=data.get("mfa") == "1",
            )
        )
    return sorted(found, key=lambda s: s.last_used_at, reverse=True)


async def close_session(user_id: str, sid: str) -> None:
    if not await redis_client.sismember(_user_sessions_key(user_id), sid):
        raise NotFoundError("Session not found", code="session_not_found")
    await _close_sessions(user_id, [sid])


def describe_device(user_agent: str, platform: str = "") -> str | None:
    """A short label from the User-Agent (and our apps' platform header): "Kuulis · Android",
    "Chrome · Windows"."""
    if not user_agent:
        return None
    ua = user_agent.lower()
    system = next((name for key, name in _SYSTEMS if key in ua), None) or _PLATFORMS.get(platform)
    browser = next((name for key, name in _BROWSERS if key in ua), None)
    app = "Kuulis" if ua.startswith(("kuulis", "okhttp", "expo")) or "cfnetwork" in ua else None
    parts = [p for p in (app or browser, system) if p]
    return " · ".join(parts) or user_agent[:60]


_SYSTEMS = (
    ("android", "Android"),
    ("iphone", "iPhone"),
    ("ipad", "iPad"),
    ("cfnetwork", "iOS"),
    ("windows", "Windows"),
    ("mac os", "macOS"),
    ("linux", "Linux"),
)
_PLATFORMS = {"android": "Android", "ios": "iOS"}
_BROWSERS = (
    ("edg/", "Edge"),
    ("opr/", "Opera"),
    ("chrome/", "Chrome"),
    ("firefox/", "Firefox"),
    ("safari/", "Safari"),
)


async def consume_one_time_token(token: str, token_type) -> dict:
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
    payload = await consume_one_time_token(token, "email_verification")
    user = await users.get_or_404(session, uuid.UUID(payload["sub"]))
    user.is_verified = True
    return user


async def request_password_reset(session: AsyncSession, email: str) -> None:
    # One email per address per minute, whatever IP asks (the route limit is per IP).
    throttle = f"{_PREFIX}:reset:{users.normalize_email(email)}"
    if not await redis_client.set(throttle, "1", nx=True, ex=60):
        return
    user = await users.get_by_email(session, email)
    if user is None or not user.is_active:
        return  # Never reveal whether an email exists.
    token, _, _ = create_token(
        str(user.id), "password_reset", timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)
    )
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    await send_templated_email.kiq(user.email, "reset", user.locale, user.full_name, link)


async def confirm_password_reset(session: AsyncSession, token: str, new_password: str) -> None:
    payload = await consume_one_time_token(token, "password_reset")
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
    users.restore_if_pending_deletion(user)
    if not user.is_active:
        raise AuthenticationError("Account disabled", code="user_inactive")
    if full_name and not user.full_name:
        user.full_name = full_name.strip()[:150]
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user
