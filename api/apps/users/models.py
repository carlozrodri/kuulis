import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kuulis.core.models import BaseModel


class Role(enum.StrEnum):
    USER = "user"
    STAFF = "staff"
    ADMIN = "admin"


ADMIN_PANEL_ROLES = frozenset({Role.STAFF, Role.ADMIN})


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(150), default="")
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=Role.USER,
        index=True,
    )
    locale: Mapped[str] = mapped_column(String(5), default="es")
    avatar_key: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="raise"
    )

    @property
    def can_access_admin(self) -> bool:
        return self.role in ADMIN_PANEL_ROLES


class SocialAccount(BaseModel):
    """Prepared for social login (Google / Apple). Not exposed by any endpoint yet."""

    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))

    user: Mapped[User] = relationship(back_populates="social_accounts", lazy="raise")
