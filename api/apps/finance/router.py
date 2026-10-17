import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from apps.audit.services import audit, note
from apps.finance import services, statements
from apps.finance.models import MonthlyClosing
from apps.finance.schemas import (
    ClosingCreate,
    ClosingRead,
    InvariantsRead,
    ReceiptRead,
    ReconcileBody,
    StatementMovements,
    StatementRead,
    StatementUpload,
)
from apps.subscriptions import services as subscriptions
from apps.subscriptions.schemas import UserBrief
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.models import User
from apps.wallet import receipts
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind
from kuulis.core import storage
from kuulis.core.calendar import add_months, local_now, month_start, parse_month
from kuulis.core.exceptions import AppError, NotFoundError

router = APIRouter(prefix="/wallet/me", tags=["finance"])
admin_router = APIRouter(prefix="/admin/finance", tags=["finance"])


def _month(value: str) -> date:
    try:
        return parse_month(value)
    except ValueError as exc:
        raise AppError("Invalid month", code="validation_error", details={"month": value}) from exc


def _brief(user: User | None) -> UserBrief | None:
    return UserBrief(id=user.id, name=user.full_name or "", email=user.email) if user else None


# --- Driver ------------------------------------------------------------------------------------


@router.get("/statements", response_model=StatementRead)
async def statement(
    user: CurrentUser,
    session: DBSession,
    month: Annotated[str | None, Query(max_length=7)] = None,
) -> StatementRead:
    """The statement of ``month`` (YYYY-MM); last month by default, or this one if it is the
    driver's first."""
    await wallet.require_driver(session, user.id)
    months = await statements.available_months(session, user.id)
    if month:
        chosen = _month(month)
    else:
        previous = add_months(month_start(local_now()), -1)
        chosen = previous if previous in months else months[0]
    st = await statements.build(session, user.id, chosen)
    moved = st.movements
    return StatementRead(
        month=st.month,
        months=st.months,
        opening_balance=st.opening_balance,
        closing_balance=st.closing_balance,
        earned=st.earned,
        counted=st.counted,
        trips=st.trips,
        tier=st.tier,
        fee=st.fee,
        estimated=st.estimated,
        charge=subscriptions.charge_read(st.charge) if st.charge else None,
        movements=StatementMovements(
            top_ups=moved[EntryKind.TOP_UP],
            promo_credits=moved[EntryKind.PROMO_CREDIT],
            transfers_in=moved[EntryKind.TRANSFER_IN],
            transfers_out=-moved[EntryKind.TRANSFER_OUT],
            fees=-moved[EntryKind.SUBSCRIPTION_FEE],
            adjustments=moved[EntryKind.ADJUSTMENT],
            referral_bonuses=moved[EntryKind.REFERRAL_BONUS],
        ),
    )


@router.get("/receipts/{receipt_id}", response_model=ReceiptRead)
async def receipt(receipt_id: uuid.UUID, user: CurrentUser, session: DBSession) -> ReceiptRead:
    row = await receipts.get_mine(session, user.id, receipt_id)
    return ReceiptRead(
        id=row.id,
        number=receipts.number_label(row.number),
        kind=row.kind,
        concept=row.concept,
        amount=row.amount,
        balance_after=row.balance_after,
        reference=row.reference,
        issued_at=row.issued_at,
        entry_id=row.entry_id,
        driver=_brief(user),
    )


# --- Admin: closings ---------------------------------------------------------------------------


async def _reads(session: DBSession, rows: list[tuple[MonthlyClosing, bool]]) -> list[ClosingRead]:
    ids = services.brief_ids([r for r, _ in rows])
    users = (
        {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    return [
        ClosingRead(
            month=row.month,
            totals=row.totals,
            hash=row.hash,
            previous_hash=row.previous_hash,
            hash_ok=ok,
            closed_by=_brief(users.get(row.closed_by_id)),
            closed_at=row.closed_at,
            statement_uploaded_at=row.statement_uploaded_at,
            has_statement_file=bool(row.binance_statement_key),
            differences=row.differences,
            has_differences=services.has_differences(row.differences),
            reconciled_at=row.reconciled_at,
            reconciled_by=_brief(users.get(row.reconciled_by_id)),
            reconcile_note=row.reconcile_note,
        )
        for row, ok in rows
    ]


async def _one(session: DBSession, month: date) -> ClosingRead:
    rows = [(r, ok) for r, ok in await services.list_closings(session) if r.month == month]
    if not rows:
        raise services.ClosingNotFoundError()
    return (await _reads(session, rows))[0]


@admin_router.get("/closings", response_model=list[ClosingRead])
async def closings(_: Can("finance.view"), session: DBSession) -> list[ClosingRead]:
    return await _reads(session, await services.list_closings(session))


@admin_router.get("/closings/preview", response_model=dict)
async def preview(
    _: Can("finance.view"), session: DBSession, month: Annotated[str, Query(max_length=7)]
) -> dict:
    """The totals a closing of ``month`` would freeze, without closing it."""
    return await services.month_totals(session, _month(month))


@admin_router.post(
    "/closings",
    dependencies=[audit("finance.close_month", "closing")],
    response_model=ClosingRead,
    status_code=201,
)
async def close(
    data: ClosingCreate, admin: Can("finance.close", verified=True), session: DBSession
) -> ClosingRead:
    row = await services.close_month(session, admin, data.month)
    note(entity_id=row.id, after={"month": data.month, "hash": row.hash})
    await session.commit()
    return await _one(session, row.month)


@admin_router.get("/closings/{month}", response_model=ClosingRead)
async def closing(month: str, _: Can("finance.view"), session: DBSession) -> ClosingRead:
    return await _one(session, _month(month))


@admin_router.post(
    "/closings/{month}/statement",
    dependencies=[audit("finance.statement_upload", "closing", "month")],
    response_model=ClosingRead,
)
async def upload_statement(
    month: str, data: StatementUpload, _: Can("finance.close"), session: DBSession
) -> ClosingRead:
    row = await services.upload_statement(session, _month(month), data.csv, data.filename)
    note(after={k: v for k, v in (row.differences or {}).items() if not isinstance(v, list)})
    await session.commit()
    return await _one(session, row.month)


@admin_router.get("/closings/{month}/statement")
async def statement_file(month: str, _: Can("finance.view"), session: DBSession) -> dict:
    row = await services.get_closing(session, _month(month))
    if not row.binance_statement_key:
        raise NotFoundError("No statement file", code="statement_not_found")
    return {"url": storage.presigned_download(row.binance_statement_key, 300)}


@admin_router.post(
    "/closings/{month}/reconcile",
    dependencies=[audit("finance.reconcile", "closing", "month")],
    response_model=ClosingRead,
)
async def reconcile(
    month: str, data: ReconcileBody, admin: Can("finance.close"), session: DBSession
) -> ClosingRead:
    row = await services.reconcile(session, admin, _month(month), (data.note or "").strip() or None)
    await session.commit()
    return await _one(session, row.month)


# --- Admin: invariants -------------------------------------------------------------------------


@admin_router.get("/invariants", response_model=InvariantsRead | None)
async def invariants(_: Can("finance.view")) -> InvariantsRead | None:
    """The last daily check (None until the first one ran)."""
    last = await services.last_invariants()
    return InvariantsRead.model_validate(last) if last else None


@admin_router.post(
    "/invariants/run",
    dependencies=[audit("finance.invariants_run", "finance")],
    response_model=InvariantsRead,
)
async def run_invariants(_: Can("finance.close"), session: DBSession) -> InvariantsRead:
    return InvariantsRead.model_validate(await services.run_invariants(session))
