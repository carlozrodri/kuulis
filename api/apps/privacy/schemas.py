import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ConsentKind = Literal["background_location", "usage_data"]


class ConsentUpdate(BaseModel):
    kind: ConsentKind
    granted: bool


class DataExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["pending", "ready", "failed", "expired"]
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    # When the next export can be asked for.
    next_at: datetime | None = None


class AdminExportRead(DataExportRead):
    user_id: uuid.UUID
    email: str
    error: str | None


class DeletionRequestRead(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    requested_at: datetime
    erase_at: datetime
    erased_at: datetime | None
