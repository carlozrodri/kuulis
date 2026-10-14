import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from apps.audit.services import audit
from apps.risk import admin, services
from apps.risk.models import HoldKind, HoldStatus, RiskKind, SignalStatus
from apps.risk.schemas import (
    BanWrite,
    BlockedRead,
    HoldRead,
    ReviewWrite,
    RiskSummary,
    RiskUserDetail,
    SignalDetail,
    SignalRead,
)
from apps.users.dependencies import Can, DBSession
from kuulis.core.pagination import Page, PageParams, page_params

admin_router = APIRouter(prefix="/admin/risk", tags=["risk"])


@admin_router.get("/summary", response_model=RiskSummary)
async def summary(_: Can("risk.view"), session: DBSession) -> RiskSummary:
    """Open alerts by kind and the money waiting for a review (badge of the Risk inbox)."""
    return await admin.summary(session)


@admin_router.get("/signals", response_model=Page[SignalRead])
async def signals(
    _: Can("risk.view"),
    session: DBSession,
    params: PageParams = Depends(page_params),
    kind: RiskKind | None = None,
    signal_status: SignalStatus | None = Query(default=SignalStatus.OPEN, alias="status"),
    user_id: uuid.UUID | None = None,
) -> Page[SignalRead]:
    """Alerts, highest score first. ``status`` defaults to open; pass it empty for all."""
    items, total = await admin.list_signals(
        session, params, kind=kind, status=signal_status, user_id=user_id
    )
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.get("/signals/{signal_id}", response_model=SignalDetail)
async def signal(signal_id: uuid.UUID, _: Can("risk.view"), session: DBSession) -> SignalDetail:
    """One alert with its evidence: the ride and its real path, the accounts involved and the
    money it holds."""
    return await admin.signal_detail(session, await admin.get_signal(session, signal_id))


async def _review(
    session: DBSession, admin_user, signal_id: uuid.UUID, value: SignalStatus, note: str | None
) -> SignalDetail:
    signal = await admin.review(session, admin_user, signal_id, value, note)
    await session.commit()
    return await admin.signal_detail(session, signal)


@admin_router.post(
    "/signals/{signal_id}/dismiss",
    response_model=SignalDetail,
    dependencies=[audit("risk.signal_dismiss", "risk_signal", "signal_id")],
)
async def dismiss(
    signal_id: uuid.UUID, data: ReviewWrite, user: Can("risk.manage"), session: DBSession
) -> SignalDetail:
    """Nothing wrong: the alert stops counting in the risk score."""
    return await _review(session, user, signal_id, SignalStatus.DISMISSED, data.note)


@admin_router.post(
    "/signals/{signal_id}/confirm",
    response_model=SignalDetail,
    dependencies=[audit("risk.signal_confirm", "risk_signal", "signal_id")],
)
async def confirm(
    signal_id: uuid.UUID, data: ReviewWrite, user: Can("risk.manage"), session: DBSession
) -> SignalDetail:
    """It was abuse: the alert keeps counting. Suspending or banning is a separate step."""
    return await _review(session, user, signal_id, SignalStatus.CONFIRMED, data.note)


@admin_router.get("/holds", response_model=Page[HoldRead])
async def holds(
    _: Can("risk.view"),
    session: DBSession,
    params: PageParams = Depends(page_params),
    hold_status: HoldStatus | None = Query(default=HoldStatus.HELD, alias="status"),
    kind: HoldKind | None = None,
    user_id: uuid.UUID | None = None,
) -> Page[HoldRead]:
    items, total = await admin.list_holds(
        session, params, status=hold_status, kind=kind, user_id=user_id
    )
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.post(
    "/holds/{hold_id}/release",
    response_model=HoldRead,
    dependencies=[audit("risk.hold_release", "risk_hold", "hold_id")],
)
async def release(
    hold_id: uuid.UUID, data: ReviewWrite, user: Can("risk.manage"), session: DBSession
) -> HoldRead:
    """Pays the promotion credit or the transfer to its recipient."""
    hold = await services.release(session, user, hold_id, data.note)
    await session.commit()
    return (await admin.hold_reads(session, [hold]))[0]


@admin_router.post(
    "/holds/{hold_id}/void",
    response_model=HoldRead,
    dependencies=[audit("risk.hold_void", "risk_hold", "hold_id")],
)
async def void(
    hold_id: uuid.UUID, data: ReviewWrite, user: Can("risk.manage"), session: DBSession
) -> HoldRead:
    """Does not pay: a promotion credit is dropped, a transfer goes back to its sender."""
    hold = await services.void(session, user, hold_id, data.note)
    await session.commit()
    return (await admin.hold_reads(session, [hold]))[0]


@admin_router.get("/users/{user_id}", response_model=RiskUserDetail)
async def user_detail(
    user_id: uuid.UUID, _: Can("risk.view"), session: DBSession
) -> RiskUserDetail:
    """Risk score, alerts, phones (with the other accounts on them), duplicates and holds."""
    return await admin.user_detail(session, user_id)


@admin_router.post(
    "/users/{user_id}/ban",
    response_model=RiskUserDetail,
    dependencies=[audit("risk.ban", "user", "user_id")],
)
async def ban(
    user_id: uuid.UUID, data: BanWrite, user: Can("risk.manage"), session: DBSession
) -> RiskUserDetail:
    """Suspends with no end date and blocks the account's email, cédula, RIF, plate, phone,
    Binance Pay ID and phones for new accounts."""
    await services.ban(session, user, user_id, data.reason)
    await session.commit()
    return await admin.user_detail(session, user_id)


@admin_router.get("/blocked", response_model=Page[BlockedRead])
async def blocked(
    _: Can("risk.view"),
    session: DBSession,
    params: PageParams = Depends(page_params),
    q: str | None = Query(default=None, max_length=100),
) -> Page[BlockedRead]:
    items, total = await admin.list_blocked(session, params, q)
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.delete(
    "/blocked/{blocked_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[audit("risk.unblock", "blocked_identifier", "blocked_id")],
)
async def unblock(blocked_id: uuid.UUID, _: Can("risk.manage"), session: DBSession) -> Response:
    await services.unblock(session, blocked_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
