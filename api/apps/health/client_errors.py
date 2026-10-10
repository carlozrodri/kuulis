"""Crash reports from the mobile app (JS errors and the last native crash), written to the logs.

Without a crash-reporting service this is how we see why the app closed on a user's phone: the
app posts the error (or, on the next launch, the native stack trace it saved) and Coolify's logs
keep it.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from apps.users.dependencies import bearer
from kuulis.core.rate_limit import limiter
from kuulis.core.security import decode_token

logger = logging.getLogger("kuulis.client_errors")

router = APIRouter(tags=["health"])


class ClientError(BaseModel):
    kind: Literal["js", "js_fatal", "render", "native"]
    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=20000)
    platform: str | None = Field(default=None, max_length=20)
    app_version: str | None = Field(default=None, max_length=40)
    route: str | None = Field(default=None, max_length=300)


def _user_id(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None:
        return None
    try:
        return str(decode_token(credentials.credentials, "access").get("sub"))
    except Exception:  # an expired token still lets the report through, without the user
        return None


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def report_client_error(
    request: Request,
    data: ClientError,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    logger.warning(
        "Client error (%s) on %s %s at %s, user %s: %s\n%s",
        data.kind,
        data.platform,
        data.app_version,
        data.route,
        _user_id(credentials),
        data.message,
        data.stack or "",
    )
