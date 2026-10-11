import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    payload: dict[str, Any]
    reason: str | None
    status: str
    requested_by_id: uuid.UUID | None
    requested_by_email: str
    decided_by_email: str | None
    decided_at: datetime | None
    decision_note: str | None
    result: dict[str, Any] | None
    expires_at: datetime
    created_at: datetime
    can_decide: bool = False


class ApprovalHeld(BaseModel):
    """Answer (202) of an endpoint whose action now waits for a second approval."""

    status: str = "pending_approval"
    approval: ApprovalRead


class ApprovalCount(BaseModel):
    pending: int


class Decision(BaseModel):
    note: str = Field(default="", max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class Rejection(Decision):
    note: str = Field(min_length=1, max_length=500)
