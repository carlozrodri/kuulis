from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class AppSetting(BaseModel):
    """One admin-editable setting. Keys without a row use the default in ``schemas.AppConfig``."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[Any] = mapped_column(JSONB)
