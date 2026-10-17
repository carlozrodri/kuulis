import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class PlaceKind(enum.StrEnum):
    HOME = "home"
    WORK = "work"
    OTHER = "other"


class SavedPlace(BaseModel):
    """A place the user saved to request rides faster ("Casa", "Trabajo", "Gym")."""

    __tablename__ = "saved_places"
    __table_args__ = (
        # One home and one work per user; any number of "other".
        Index(
            "uq_saved_places_user_kind",
            "user_id",
            "kind",
            unique=True,
            postgresql_where=text("kind IN ('home', 'work')"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[PlaceKind] = mapped_column(
        Enum(PlaceKind, name="place_kind", values_callable=lambda e: [m.value for m in e])
    )
    label: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    # Doc 23: icon of an "other" place (schemas.PlaceIcon); home and work have their own.
    icon: Mapped[str | None] = mapped_column(String(16))
