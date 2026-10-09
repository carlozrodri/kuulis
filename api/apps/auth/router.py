from fastapi import APIRouter, Request, status

from apps.auth import services
from apps.auth.schemas import (
    AuthResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    TokenRequest,
)
from apps.users import services as users
from apps.users.dependencies import CurrentUser, DBSession
from apps.users.schemas import UserCreate, UserRead
from kuulis.core.exceptions import NotImplementedAppError, PermissionDeniedError
from kuulis.core.rate_limit import limiter
from kuulis.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(request: Request, data: RegisterRequest, session: DBSession) -> AuthResponse:
    user = await users.create_user(session, UserCreate(**data.model_dump()))
    await session.commit()
    await services.send_verification_email(user)
    tokens = await services.issue_tokens(user)
    return AuthResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, data: LoginRequest, session: DBSession) -> AuthResponse:
    user = await users.authenticate(session, data.email, data.password)
    tokens = await services.issue_tokens(user)
    return AuthResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/admin/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def admin_login(request: Request, data: LoginRequest, session: DBSession) -> AuthResponse:
    """Same as /login but only staff/admin roles can obtain tokens (used by the admin panel)."""
    user = await users.authenticate(session, data.email, data.password)
    if not user.can_access_admin:
        raise PermissionDeniedError("Admin access required", code="admin_required")
    tokens = await services.issue_tokens(user)
    return AuthResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(request: Request, data: RefreshRequest, session: DBSession) -> TokenPair:
    _, tokens = await services.rotate_refresh_token(session, data.refresh_token)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest) -> None:
    await services.revoke(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser) -> None:
    await services.revoke_all(str(user.id))


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


@router.post("/social/{provider}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def social_login(provider: str) -> None:
    """Placeholder: social login (Google / Apple) is planned, see docs/roadmap.md."""
    raise NotImplementedAppError(
        f"Social login with {provider} is not available yet", code="social_login_not_available"
    )
