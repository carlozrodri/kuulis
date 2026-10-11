from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class StaffRole(BaseModel):
    """A set of admin permissions given to staff accounts (``users.staff_role_id``)."""

    __tablename__ = "staff_roles"

    name: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
