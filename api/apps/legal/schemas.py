from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["terms", "privacy", "community", "driver_terms", "wallet"]
AcceptKind = Literal["terms", "privacy", "driver_terms", "wallet"]
Locale = Literal["es", "en"]


class LegalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    version: int
    locale: str
    title: str
    body_md: str
    summary: str
    requires_reacceptance: bool
    published_at: datetime


class LegalVersionSummary(BaseModel):
    """A document without its text (lists)."""

    model_config = ConfigDict(from_attributes=True)

    kind: str
    version: int
    locale: str
    title: str
    summary: str
    requires_reacceptance: bool
    published_at: datetime


class Accept(BaseModel):
    kinds: list[AcceptKind] = Field(min_length=1, max_length=4)


class AcceptanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    version: int
    ip: str | None
    platform: str | None
    created_at: datetime


class LocaleText(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body_md: str = Field(min_length=20, max_length=100_000)


class Publish(BaseModel):
    es: LocaleText
    en: LocaleText
    summary: str = Field(default="", max_length=500)
    requires_reacceptance: bool = False
