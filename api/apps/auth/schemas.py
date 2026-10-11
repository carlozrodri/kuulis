from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from apps.users.schemas import Locale, UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=150)
    locale: Locale = "es"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(TokenPair):
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenRequest(BaseModel):
    token: str


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=8192)


class AppleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=8192)
    # Apple only shares the name on the first authorization; the app forwards it here.
    full_name: str | None = Field(default=None, max_length=150)


class SessionRead(BaseModel):
    id: str
    current: bool
    device: str | None
    platform: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime
    admin: bool  # opened in the admin panel with the second factor


class AdminLoginStep(BaseModel):
    """First step of the admin login: the password was right, now the second factor.

    ``totp_setup`` comes when the account has no authenticator yet: scan ``setup.qr_data_uri``
    (or type ``setup.secret``) and confirm with a code."""

    status: Literal["totp_required", "totp_setup"]
    challenge: str
    setup: "TotpSetup | None" = None


class TotpSetup(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_uri: str


class TotpVerify(BaseModel):
    challenge: str = Field(min_length=10, max_length=100)
    code: str = Field(min_length=6, max_length=20)  # 6 digits, or a recovery code


class AdminAuthResponse(AuthResponse):
    recovery_codes: list[str] | None = None  # only once, right after setting up the authenticator


class ReauthRequest(BaseModel):
    code: str = Field(min_length=6, max_length=20)
