import uuid

from fastapi import APIRouter, Query

from apps.approvals import services
from apps.approvals.schemas import ApprovalCount, ApprovalRead, Decision, Rejection
from apps.audit.services import audit
from apps.users.dependencies import DBSession, StaffUser, ensure_recently_verified

router = APIRouter(prefix="/admin/approvals", tags=["approvals"])

# Open to every staff account: what each one sees and may decide depends on the action's
# permission, checked per request in apps.approvals.services.


@router.get("", response_model=list[ApprovalRead])
async def approvals(
    user: StaffUser,
    session: DBSession,
    status: str | None = Query(default=None, pattern=r"^(pending|approved|rejected|expired)$"),
) -> list[ApprovalRead]:
    return await services.visible(session, user, status)


@router.get("/count", response_model=ApprovalCount)
async def count(user: StaffUser, session: DBSession) -> ApprovalCount:
    return ApprovalCount(pending=await services.pending_for(session, user))


async def _read(session: DBSession, user, row) -> ApprovalRead:
    read = ApprovalRead.model_validate(row)
    read.can_decide = await services.can_decide(session, user, row)
    return read


@router.post(
    "/{approval_id}/approve",
    dependencies=[audit("approval.approve", "approval", "approval_id")],
    response_model=ApprovalRead,
)
async def approve(
    approval_id: uuid.UUID, data: Decision, user: StaffUser, session: DBSession
) -> ApprovalRead:
    await ensure_recently_verified(user)
    row = await services.approve(session, user, approval_id, data.note)
    await session.commit()
    await services.after_commit(row)
    return await _read(session, user, row)


@router.post(
    "/{approval_id}/reject",
    dependencies=[audit("approval.reject", "approval", "approval_id")],
    response_model=ApprovalRead,
)
async def reject(
    approval_id: uuid.UUID, data: Rejection, user: StaffUser, session: DBSession
) -> ApprovalRead:
    row = await services.reject(session, user, approval_id, data.note)
    await session.commit()
    return await _read(session, user, row)
