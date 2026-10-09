from pydantic import BaseModel, Field


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Place(Point):
    """A point with a human address (pickup / dropoff)."""

    address: str = Field(default="", max_length=300)


class GeoResult(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
