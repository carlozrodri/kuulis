import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.places.models import PlaceKind

# Icon of an "other" place; the app maps each to a glyph. Ignored for home and work.
PlaceIcon = Literal["star", "heart", "dumbbell", "school", "store", "users", "utensils", "hospital"]


class PlaceWrite(BaseModel):
    kind: PlaceKind = PlaceKind.OTHER
    # Shown instead of the address ("Gym", "Casa de mamá"); home and work use their own name.
    label: str = Field(default="", max_length=40)
    address: str = Field(min_length=1, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    icon: PlaceIcon | None = None


class PlaceUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, min_length=1, max_length=300)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    icon: PlaceIcon | None = None


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: PlaceKind
    label: str
    address: str
    lat: float
    lng: float
    icon: str | None = None
    updated_at: datetime
