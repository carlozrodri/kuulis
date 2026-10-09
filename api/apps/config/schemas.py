from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from apps.drivers.models import DocumentKind, VehicleType

MinYear = Annotated[int, Field(ge=1950, le=2100)]


def _unique[T](values: list[T]) -> list[T]:
    if len(set(values)) != len(values):
        raise ValueError("values must be unique")
    return values


class AppConfig(BaseModel):
    """Every admin-editable setting with its default. Adding a key here is enough to expose it."""

    driver_min_age: int = Field(default=21, ge=16, le=99)
    vehicle_min_year: dict[VehicleType, MinYear] = Field(
        default_factory=lambda: {VehicleType.MOTO: 2013, VehicleType.CAR: 1993}
    )
    enabled_vehicle_types: list[VehicleType] = Field(
        default_factory=lambda: [VehicleType.MOTO], min_length=1
    )
    driver_required_documents: list[DocumentKind] = Field(
        default_factory=lambda: [
            DocumentKind.ID_CARD,
            DocumentKind.RIF,
            DocumentKind.DRIVERS_LICENSE,
            DocumentKind.MEDICAL_CERTIFICATE,
            DocumentKind.VEHICLE_REGISTRATION,
            DocumentKind.SELFIE,
            DocumentKind.VEHICLE_PHOTO,
        ]
    )
    vehicle_photo_min_count: int = Field(default=2, ge=0, le=10)

    @field_validator("enabled_vehicle_types", "driver_required_documents")
    @classmethod
    def check_unique(cls, value: list) -> list:
        return _unique(value)

    def min_year(self, vehicle_type: VehicleType) -> int:
        return self.vehicle_min_year.get(vehicle_type, 0)


class AppConfigUpdate(BaseModel):
    """Partial update. ``vehicle_min_year`` is merged per vehicle type."""

    driver_min_age: int | None = Field(default=None, ge=16, le=99)
    vehicle_min_year: dict[VehicleType, MinYear] | None = None
    enabled_vehicle_types: list[VehicleType] | None = Field(default=None, min_length=1)
    driver_required_documents: list[DocumentKind] | None = None
    vehicle_photo_min_count: int | None = Field(default=None, ge=0, le=10)

    @field_validator("enabled_vehicle_types", "driver_required_documents")
    @classmethod
    def check_unique(cls, value: list | None) -> list | None:
        return value if value is None else _unique(value)
