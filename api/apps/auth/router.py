from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from apps.audit.services import audit
from apps.auth import services, social, totp
from apps.auth.schemas import (
    AdminAuthResponse,
    AdminLoginStep,
    AppleLoginRequest,
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ReauthRequest,
    RefreshRequest,
    RegisterRequest,
    SessionRead,
    TokenPair,
    TokenRequest,
    TotpVerify,
)
from apps.legal import services as legal
from apps.moderation import services as moderation
from apps.users import passwords
from apps.users import services as users
from apps.users.dependencies import CurrentUser, DBSession, StaffUser
from apps.users.schemas import UserCreate, UserRead
from kuulis.core.exceptions import PermissionDeniedError
from kuulis.core.rate_limit import limiter
from kuulis.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(request: Request, data: RegisterRequest, session: DBSession) -> AuthResponse:
    passwords.ensure_allowed(data.password)
    user = await users.create_user(session, UserCreate(**data.model_dump(exclude={"accept_legal"})))
    if data.accept_legal:
        await legal.accept(session, user, list(legal.FOR_EVERYONE), request)
    await session.commit()
    await services.send_verification_email(user)
    tokens = await services.issue_tokens(user, request)
    return AuthResponse(**tokens.model_dump(), user=await moderation.user_read(session, user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, data: LoginRequest, session: DBSession) -> AuthResponse:
    user = await services.password_login(session, data.email, data.password)
    tokens = await services.issue_tokens(user, request)
    return AuthResponse(**tokens.model_dump(), user=await moderation.user_read(session, user))


@router.post("/admin/login", response_model=AdminLoginStep | AdminAuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def admin_login(
    request: Request, data: LoginRequest, session: DBSession
) -> AdminLoginStep | AdminAuthResponse:
    """Password step of the admin panel login (staff/admin only). Answers with the second-factor
    step (``POST /auth/admin/totp`` completes it); tokens straight away only when
    ADMIN_TOTP_REQUIRED is off."""
    user = await services.password_login(session, data.email, data.password)
    if not user.can_access_admin:
        raise PermissionDeniedError("Admin access required", code="admin_required")
    if settings.ADMIN_TOTP_REQUIRED:
        step = await totp.start_admin_login(session, user)
        await session.rollback()  # the password login touched last_login_at: set it on success
        return step
    tokens = await services.issue_tokens(user, request)
    return AdminAuthResponse(**tokens.model_dump(), user=await moderation.user_read(session, user))


@router.post("/admin/totp", response_model=AdminAuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def admin_totp(request: Request, data: TotpVerify, session: DBSession) -> AdminAuthResponse:
    """Second step: a code from the authenticator (or a recovery code). Right after setting the
    authenticator up, the answer carries the recovery codes, shown only this once."""
    user, recovery_codes = await totp.complete_admin_login(session, data.challenge, data.code)
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    tokens = await services.issue_tokens(user, request, mfa=True)
    return AdminAuthResponse(
        **tokens.model_dump(),
        user=await moderation.user_read(session, user),
        recovery_codes=recovery_codes,
    )


@router.post(
    "/admin/reauth",
    dependencies=[audit("auth.reauth", "user")],
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("10/minute")
async def admin_reauth(
    request: Request, data: ReauthRequest, user: StaffUser, session: DBSession
) -> None:
    """Confirms a sensitive action with a fresh code (valid 10 minutes on this session)."""
    if not user.auth_sid:
        raise PermissionDeniedError("Sign in to the admin panel", code="admin_mfa_required")
    await totp.reauthenticate(session, user, user.auth_sid, data.code)
    await session.commit()


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(settings.RATE_LIMIT_REFRESH)
async def refresh(request: Request, data: RefreshRequest, session: DBSession) -> TokenPair:
    _, tokens = await services.rotate_refresh_token(session, data.refresh_token, request)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest) -> None:
    await services.revoke(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser) -> None:
    await services.revoke_all(str(user.id))


@router.get("/sessions", response_model=list[SessionRead])
async def sessions(user: CurrentUser) -> list[SessionRead]:
    """Open sessions of the user (one per signed-in device), the current one marked."""
    return await services.list_sessions(str(user.id), user.auth_sid)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_session(session_id: str, user: CurrentUser) -> None:
    await services.close_session(str(user.id), session_id)


@router.post("/verify-email", response_model=UserRead)
async def verify_email(data: TokenRequest, session: DBSession) -> UserRead:
    return UserRead.model_validate(await services.verify_email(session, data.token))


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def resend_verification(request: Request, user: CurrentUser) -> None:
    if not user.is_verified:
        await services.send_verification_email(user)


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def password_reset(request: Request, data: PasswordResetRequest, session: DBSession) -> None:
    await services.request_password_reset(session, data.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def password_reset_confirm(
    request: Request, data: PasswordResetConfirm, session: DBSession
) -> None:
    await services.confirm_password_reset(session, data.token, data.new_password)


@router.post("/social/google", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_login(
    request: Request, data: GoogleLoginRequest, session: DBSession
) -> AuthResponse:
    identity = await social.verify_google_token(data.id_token)
    user = await services.social_login(session, identity)
    await session.commit()
    tokens = await services.issue_tokens(user, request)
    return AuthResponse(**tokens.model_dump(), user=await moderation.user_read(session, user))


@router.post("/social/apple", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def apple_login(
    request: Request, data: AppleLoginRequest, session: DBSession
) -> AuthResponse:
    identity = await social.verify_apple_token(data.id_token)
    user = await services.social_login(session, identity, data.full_name)
    await session.commit()
    tokens = await services.issue_tokens(user, request)
    return AuthResponse(**tokens.model_dump(), user=await moderation.user_read(session, user))
