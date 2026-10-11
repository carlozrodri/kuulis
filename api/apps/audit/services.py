"""Audit log of the admin (doc 06): who did what, to which record, when and from where.

Admin endpoints declare their action with ``audit("wallet.adjust", "wallet", "user_id")``.
The dependency opens an entry for the request (actor, IP, user agent, request id, the target id from
the path and the request body without secrets as ``after``); services can add the real
``before``/``after`` with :func:`note`. The request's DB session writes the entry right before it
commits (``kuulis.core.db.get_db``), so the action and its audit row land in the same transaction
and a failed request leaves none.
"""

import json
import uuid
from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import Request
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.audit.models import AuditLog
from kuulis.core.request_context import audit_ctx, request_id_ctx

SECRET_KEYS = {"password", "token", "secret", "passphrase", "totp", "recovery_codes", "api_key"}
SECRET_SUFFIXES = ("_password", "_token", "_secret", "_passphrase")
MAX_VALUE_CHARS = 2000


def _redact(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if lowered in SECRET_KEYS or lowered.endswith(SECRET_SUFFIXES):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_redact(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
        return value[:MAX_VALUE_CHARS] + "…"
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def snapshot(obj: Any, fields: Iterable[str]) -> dict[str, Any]:
    """The listed attributes of a model (or keys of a dict), JSON-safe and without secrets."""
    if isinstance(obj, dict):
        return _redact({f: obj.get(f) for f in fields})
    return _redact({f: getattr(obj, f, None) for f in fields})


def _holder() -> dict | None:
    return audit_ctx.get()


def begin(
    action: str,
    entity_type: str,
    entity_id: object = None,
    *,
    actor: Any = None,
    request: Request | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Opens the audit entry of this request (endpoints that audit only some cases call it
    directly, e.g. staff opening someone else's file)."""
    holder = _holder()
    if holder is None:  # outside an HTTP request (worker, scripts, tests calling services)
        return
    holder["entry"] = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "actor_id": getattr(actor, "id", None),
        "actor_email": getattr(actor, "email", "") or "",
        "before": None,
        "after": after,
        "reason": None,
        "ip": request.client.host if request and request.client else None,
        "user_agent": (request.headers.get("user-agent") or "")[:300] if request else None,
        "request_id": request_id_ctx.get(),
    }
    holder.pop("row", None)


def note(
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    entity_id: object = None,
) -> None:
    """Adds detail to the open entry: the record before and after the change, the reason, or the
    id of a record created by the action."""
    holder = _holder() or {}
    entry = holder.get("entry")
    if entry is None:
        return
    changes: dict[str, Any] = {}
    if before is not None:
        changes["before"] = _redact(before)
    if after is not None:
        changes["after"] = _redact(after)
    if reason:
        changes["reason"] = reason
    if entity_id is not None:
        changes["entity_id"] = str(entity_id)
    entry.update(changes)
    row = holder.get("row")
    if row is not None:  # already staged by an earlier commit: the request's last commit saves it
        for key, value in changes.items():
            setattr(row, key, value)


def stage(session: Session) -> None:
    """Adds the open entry to ``session``. ``get_db`` runs it on the session's ``before_commit``
    event, so the row commits with the first commit that follows the action, also when the
    endpoint commits by itself."""
    holder = _holder() or {}
    entry = holder.get("entry")
    if entry is None or "row" in holder:
        return
    holder["row"] = AuditLog(**entry)
    session.add(holder["row"])


def audited(action: str, entity_type: str, id_param: str | None = None) -> Callable:
    """Dependency for an admin endpoint (or a sensitive read): every successful call leaves an
    audit row."""
    from apps.users.dependencies import CurrentUser  # avoids an import cycle

    async def _open(request: Request, user: CurrentUser) -> None:
        body: dict[str, Any] | None = None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                raw = await request.body()
                parsed = json.loads(raw) if raw else None
                body = parsed if isinstance(parsed, dict) else None
            except ValueError:
                body = None
        elif request.query_params:  # a sensitive read: keep its filters
            body = dict(request.query_params)
        begin(
            action,
            entity_type,
            request.path_params.get(id_param) if id_param else None,
            actor=user,
            request=request,
            after=_redact(body) if body else None,
        )
        if body and isinstance(body.get("reason"), str):
            note(reason=body["reason"].strip() or None)

    _open.audit_action = action  # type: ignore[attr-defined]
    return _open


# --- Queries ------------------------------------------------------------------------------------


def query(
    *,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Select[tuple[AuditLog]]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at < until)
    return stmt


def audit(action: str, entity_type: str, id_param: str | None = None) -> Any:
    """``dependencies=[audit("wallet.adjust", "wallet", "user_id")]`` on an admin route."""
    from fastapi import Depends

    return Depends(audited(action, entity_type, id_param))
