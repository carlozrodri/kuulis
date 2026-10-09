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
