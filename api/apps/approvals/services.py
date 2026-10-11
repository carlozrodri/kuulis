"""Four-eyes approvals (doc 06): high-impact admin actions wait until a second person approves.

An endpoint asks :func:`required` whether its action needs approval; if so it calls :func:`hold`
and answers 202 with the request instead of acting. Approving runs the action registered in
``ACTIONS`` with the stored payload, inside the approver's transaction (so a failing action leaves
the request pending). Whoever asked can never approve; the approver needs the action's permission
(admins only for admin-only actions) and a fresh second-factor code.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.approvals.models import ApprovalStatus, PendingApproval
from apps.approvals.schemas import ApprovalHeld, ApprovalRead
from apps.audit.services import _redact, note
from apps.staff.services import permissions_of
from apps.users.models import Role, User
from kuulis.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError

EXPIRES_AFTER = timedelta(hours=48)

Executor = Callable[[AsyncSession, User, dict[str, Any]], Awaitable[dict[str, Any] | None]]
AfterCommit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class Action:
    permission: str | None  # None: admins only
    execute: Executor  # inside the approver's transaction
    after_commit: AfterCommit | None = None  # side effects once it committed (cache, pushes)


class ApprovalNotFoundError(NotFoundError):
    code = "approval_not_found"
    message = "Approval request not found"


class ApprovalClosedError(ConflictError):
    code = "approval_closed"
    message = "This request was already decided or expired"


class OwnApprovalError(PermissionDeniedError):
    code = "approval_own_request"
    message = "Someone else has to approve your request"


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Actions ------------------------------------------------------------------------------------


async def _wallet_adjust(session: AsyncSession, requester: User, p: dict) -> dict:
    from apps.wallet import services as wallet

    entry = await wallet.adjust(
        session, requester, uuid.UUID(p["user_id"]), Decimal(p["amount"]), p["reason"]
    )
    await session.flush()
    return {"entry_id": str(entry.id)}


async def _fee_schedule(session: AsyncSession, requester: User, p: dict) -> dict:
    from apps.subscriptions import services as subscriptions
    from apps.subscriptions.schemas import ScheduleCreate

    data = ScheduleCreate.model_validate(p)
    row = await subscriptions.create_schedule(session, requester, data.effective_month, data.tiers)
    await session.flush()
    return {"schedule_id": str(row.id)}


async def _config_update(session: AsyncSession, requester: User, p: dict) -> None:
    from apps.config import services as config
    from apps.config.schemas import AppConfigUpdate

    await config.update_app_config(session, AppConfigUpdate.model_validate(p))


async def _config_cache(p: dict) -> None:
    from apps.config import services as config

    await config.invalidate_cache()


async def _nothing(session: AsyncSession, requester: User, p: dict) -> None:
    return None


async def _broadcast(p: dict) -> None:
    from apps.notifications import tasks

    await tasks.broadcast.kiq(p["title"], p["body"], p["data"], p.get("role"))


ACTIONS: dict[str, Action] = {
    "wallet.adjust": Action("wallet.adjust", _wallet_adjust),
    "fee_schedule.create": Action(None, _fee_schedule),
    "config.update": Action(None, _config_update, _config_cache),
    "notification.broadcast": Action("notifications.send", _nothing, _broadcast),
}


# --- Asking -------------------------------------------------------------------------------------


async def required(session: AsyncSession, action: str, **facts: Any) -> bool:
    """Whether ``action`` (with these facts) needs a second approval under the current settings."""
    from apps.config.services import get_app_config

    config = await get_app_config(session)
    if action == "wallet.adjust":
        limit = config.approval_adjust_limit
        return limit > 0 and abs(facts["amount"]) > limit
    if action in ("fee_schedule.create", "config.update"):
        return config.approval_fares
    if action == "notification.broadcast":
        return config.approval_broadcasts
    return False


async def hold(
    session: AsyncSession,
    requester: User,
    action: str,
    *,
    entity_type: str,
    entity_id: object = None,
    summary: str,
    payload: dict[str, Any],
    reason: str | None = None,
) -> JSONResponse:
    """Stores the request and answers 202; the request's audit row becomes ``approval.request``."""
    if action not in ACTIONS:
        raise ValueError(f"No approval action {action!r}")
    row = PendingApproval(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary=summary[:300],
        payload=_redact(payload),
        reason=reason,
        status=ApprovalStatus.PENDING,
        requested_by_id=requester.id,
        requested_by_email=requester.email,
        expires_at=utcnow() + EXPIRES_AFTER,
    )
    session.add(row)
    await session.flush()
    note(
        action="approval.request",
        entity_type="approval",
        entity_id=row.id,
        after={"action": action, "summary": row.summary, "payload": row.payload},
    )
    await session.commit()
    await session.refresh(row)
    body = ApprovalHeld(approval=ApprovalRead.model_validate(row))
    return JSONResponse(body.model_dump(mode="json"), status_code=status.HTTP_202_ACCEPTED)


# --- Deciding -----------------------------------------------------------------------------------


def _expired(row: PendingApproval) -> bool:
    return row.status == ApprovalStatus.PENDING and row.expires_at <= utcnow()


async def can_decide(session: AsyncSession, user: User, row: PendingApproval) -> bool:
    if row.status != ApprovalStatus.PENDING or _expired(row) or row.requested_by_id == user.id:
        return False
    permission = ACTIONS[row.action].permission
    if permission is None:
        return user.role == Role.ADMIN
    return permission in await permissions_of(session, user)


async def _can_see(session: AsyncSession, user: User, row: PendingApproval) -> bool:
    if user.role == Role.ADMIN or row.requested_by_id == user.id:
        return True
    permission = ACTIONS[row.action].permission
    return permission is not None and permission in await permissions_of(session, user)


async def visible(
    session: AsyncSession, user: User, status_filter: str | None = None, limit: int = 200
) -> list[ApprovalRead]:
    stmt = select(PendingApproval).order_by(PendingApproval.created_at.desc()).limit(limit)
    if status_filter == ApprovalStatus.PENDING:
        stmt = stmt.where(
            PendingApproval.status == ApprovalStatus.PENDING,
            PendingApproval.expires_at > utcnow(),
        )
    elif status_filter:
        stmt = stmt.where(PendingApproval.status == status_filter)
    out = []
    for row in await session.scalars(stmt):
        if not await _can_see(session, user, row):
            continue
        read = ApprovalRead.model_validate(row)
        if _expired(row):
            read.status = ApprovalStatus.EXPIRED
        read.can_decide = await can_decide(session, user, row)
        out.append(read)
    return out


async def pending_for(session: AsyncSession, user: User) -> int:
    rows = await session.scalars(
        select(PendingApproval).where(
            PendingApproval.status == ApprovalStatus.PENDING,
            PendingApproval.expires_at > utcnow(),
        )
    )
    return sum([await can_decide(session, user, row) for row in rows])


async def _open(session: AsyncSession, user: User, approval_id: uuid.UUID) -> PendingApproval:
    row = await session.scalar(
        select(PendingApproval).where(PendingApproval.id == approval_id).with_for_update()
    )
    if row is None or not await _can_see(session, user, row):
        raise ApprovalNotFoundError()
    if row.status != ApprovalStatus.PENDING or _expired(row):
        raise ApprovalClosedError()
    if row.requested_by_id == user.id:
        raise OwnApprovalError()
    if not await can_decide(session, user, row):
        permission = ACTIONS[row.action].permission
        raise PermissionDeniedError(
            "Your role cannot approve this", details={"permission": permission or "admin"}
        )
    return row


def _decided(row: PendingApproval, user: User, status_: ApprovalStatus, text: str) -> None:
    row.status = status_
    row.decided_by_id = user.id
    row.decided_by_email = user.email
    row.decided_at = utcnow()
    row.decision_note = text or None


async def approve(
    session: AsyncSession, user: User, approval_id: uuid.UUID, text: str = ""
) -> PendingApproval:
    row = await _open(session, user, approval_id)
    requester = await session.get(User, row.requested_by_id) if row.requested_by_id else None
    # The action runs first: if it fails (e.g. not enough balance) the request stays pending.
    # It is recorded as done by whoever asked (or the approver if that account is gone).
    result = await ACTIONS[row.action].execute(session, requester or user, row.payload)
    _decided(row, user, ApprovalStatus.APPROVED, text)
    row.result = result
    note(
        before={"status": ApprovalStatus.PENDING},
        after={"status": row.status, "action": row.action, "result": result},
    )
    await session.flush()
    return row


async def after_commit(row: PendingApproval) -> None:
    """Side effects of an approved action; the router calls it once the approval committed."""
    hook = ACTIONS[row.action].after_commit
    if hook is not None and row.status == ApprovalStatus.APPROVED:
        await hook(row.payload)


async def reject(
    session: AsyncSession, user: User, approval_id: uuid.UUID, text: str
) -> PendingApproval:
    row = await _open(session, user, approval_id)
    _decided(row, user, ApprovalStatus.REJECTED, text)
    note(before={"status": ApprovalStatus.PENDING}, after={"status": row.status}, reason=text)
    await session.flush()
    return row
