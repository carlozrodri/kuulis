"""Reads for the admin's Risk inbox and the risk part of a user's page (doc 16)."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.drivers import verification
from apps.drivers.models import DriverProfile
from apps.moderation import services as moderation
from apps.rides.models import Ride
from apps.risk import services
from apps.risk.models import (
    BlockedIdentifier,
    DeviceFingerprint,
    HoldKind,
    HoldStatus,
    RiskHold,
    RiskKind,
    RiskSignal,
    SignalStatus,
)
from apps.risk.schemas import (
    BlockedRead,
    DeviceRead,
    HoldRead,
    KindCount,
    RideEvidence,
    RiskSummary,
    RiskUser,
    RiskUserDetail,
    SignalDetail,
    SignalRead,
)
from apps.safety import track
from apps.safety.models import RideTrack
from apps.users.models import User
from kuulis.core.pagination import PageParams


class People:
    """Loads users (and their driver profile ids) once for a page of rows."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.profiles: dict[uuid.UUID, uuid.UUID] = {}

    async def load(self, session: AsyncSession, ids: Iterable[uuid.UUID | None]) -> "People":
        wanted = {i for i in ids if i is not None} - set(self.users)
        if wanted:
            for user in await session.scalars(select(User).where(User.id.in_(wanted))):
                self.users[user.id] = user
            rows = await session.execute(
                select(DriverProfile.user_id, DriverProfile.id).where(
                    DriverProfile.user_id.in_(wanted)
                )
            )
            self.profiles.update(dict(rows.all()))
        return self

    def brief(self, user_id: uuid.UUID | None) -> RiskUser | None:
        user = self.users.get(user_id) if user_id else None
        if user is None:
            return None
        return RiskUser(
            id=user.id,
            name=user.full_name or "",
            email=None if user.deleted_at else user.email,
            risk_score=user.risk_score,
            driver_profile_id=self.profiles.get(user.id),
        )

    def name(self, user_id: uuid.UUID | None) -> str | None:
        user = self.users.get(user_id) if user_id else None
        return (user.full_name or user.email) if user else None


def _signal_ids(signal: RiskSignal) -> list[uuid.UUID | None]:
    return [signal.user_id, signal.related_user_id, signal.reviewed_by_id]


def signal_read(signal: RiskSignal, people: People) -> SignalRead:
    user = people.brief(signal.user_id)
    assert user is not None
    return SignalRead(
        id=signal.id,
        kind=signal.kind,
        reasons=signal.reasons,
        score=signal.score,
        status=signal.status,
        evidence=signal.evidence,
        user=user,
        related_user=people.brief(signal.related_user_id),
        ride_id=signal.ride_id,
        created_at=signal.created_at,
        reviewed_by_name=people.name(signal.reviewed_by_id),
        reviewed_at=signal.reviewed_at,
        review_note=signal.review_note,
    )


def hold_read(hold: RiskHold, people: People) -> HoldRead:
    user = people.brief(hold.user_id)
    assert user is not None
    return HoldRead(
        id=hold.id,
        kind=hold.kind,
        status=hold.status,
        amount=hold.amount,
        user=user,
        sender=people.brief(hold.sender_id),
        ride_id=hold.ride_id,
        reasons=hold.reasons,
        release_at=hold.release_at,
        created_at=hold.created_at,
        resolved_at=hold.resolved_at,
        resolved_by_name=people.name(hold.resolved_by_id),
        note=hold.note,
    )


async def signal_reads(session: AsyncSession, signals: list[RiskSignal]) -> list[SignalRead]:
    people = await People().load(session, (i for s in signals for i in _signal_ids(s)))
    return [signal_read(s, people) for s in signals]


async def hold_reads(session: AsyncSession, holds: list[RiskHold]) -> list[HoldRead]:
    people = await People().load(
        session, (i for h in holds for i in (h.user_id, h.sender_id, h.resolved_by_id))
    )
    return [hold_read(h, people) for h in holds]


async def list_signals(
    session: AsyncSession,
    params: PageParams,
    *,
    kind: RiskKind | None,
    status: SignalStatus | None,
    user_id: uuid.UUID | None,
) -> tuple[list[SignalRead], int]:
    stmt = select(RiskSignal)
    if kind is not None:
        stmt = stmt.where(RiskSignal.kind == kind)
    if status is not None:
        stmt = stmt.where(RiskSignal.status == status)
    if user_id is not None:
        stmt = stmt.where(or_(RiskSignal.user_id == user_id, RiskSignal.related_user_id == user_id))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(
        await session.scalars(
            stmt.order_by(RiskSignal.score.desc(), RiskSignal.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
        )
    )
    return await signal_reads(session, rows), int(total or 0)


async def get_signal(session: AsyncSession, signal_id: uuid.UUID) -> RiskSignal:
    signal = await session.get(RiskSignal, signal_id)
    if signal is None:
        raise services.SignalNotFoundError()
    return signal


async def _ride_evidence(session: AsyncSession, ride_id: uuid.UUID) -> RideEvidence | None:
    ride = await session.get(Ride, ride_id)
    if ride is None:
        return None
    stored = await session.scalar(select(RideTrack.points).where(RideTrack.ride_id == ride_id))
    points = stored if stored is not None else track.thin(await track.buffered(ride_id))
    return RideEvidence(
        id=ride.id,
        status=ride.status.value,
        pickup=[ride.pickup_lat, ride.pickup_lng],
        dropoff=[ride.dropoff_lat, ride.dropoff_lng],
        distance_m=ride.distance_m,
        duration_s=ride.duration_s,
        discount=ride.discount,
        started_at=ride.started_at,
        completed_at=ride.completed_at,
        track=points,
    )


async def signal_detail(session: AsyncSession, signal: RiskSignal) -> SignalDetail:
    account_ids: list[uuid.UUID] = []
    if signal.kind == RiskKind.SHARED_DEVICE:
        for raw in signal.evidence.get("accounts", []):
            try:
                account_ids.append(uuid.UUID(raw))
            except ValueError:
                continue
    else:
        account_ids = [i for i in (signal.user_id, signal.related_user_id) if i]
    for key in ("sender_id", "recipient_id"):
        if raw := signal.evidence.get(key):
            account_ids.append(uuid.UUID(raw))
    people = await People().load(session, [*_signal_ids(signal), *account_ids])
    holds: list[RiskHold] = []
    if signal.ride_id is not None:
        holds = list(
            await session.scalars(
                select(RiskHold).where(
                    RiskHold.ride_id == signal.ride_id, RiskHold.kind == HoldKind.PROMO_CREDIT
                )
            )
        )
    elif entry_id := signal.evidence.get("entry_id"):
        holds = list(
            await session.scalars(select(RiskHold).where(RiskHold.entry_id == uuid.UUID(entry_id)))
        )
    seen: set[uuid.UUID] = set()
    accounts = []
    for i in account_ids:
        brief = people.brief(i)
        if brief is not None and i not in seen:
            seen.add(i)
            accounts.append(brief)
    return SignalDetail(
        **signal_read(signal, people).model_dump(),
        ride=await _ride_evidence(session, signal.ride_id) if signal.ride_id else None,
        accounts=accounts,
        holds=await hold_reads(session, holds),
    )


async def list_holds(
    session: AsyncSession,
    params: PageParams,
    *,
    status: HoldStatus | None,
    kind: HoldKind | None,
    user_id: uuid.UUID | None = None,
) -> tuple[list[HoldRead], int]:
    stmt = select(RiskHold)
    if status is not None:
        stmt = stmt.where(RiskHold.status == status)
    if kind is not None:
        stmt = stmt.where(RiskHold.kind == kind)
    if user_id is not None:
        stmt = stmt.where(or_(RiskHold.user_id == user_id, RiskHold.sender_id == user_id))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(
        await session.scalars(
            stmt.order_by(RiskHold.created_at.desc()).limit(params.limit).offset(params.offset)
        )
    )
    return await hold_reads(session, rows), int(total or 0)


async def blocked_reads(session: AsyncSession, rows: list[BlockedIdentifier]) -> list[BlockedRead]:
    people = await People().load(
        session, (i for b in rows for i in (b.source_user_id, b.created_by_id))
    )
    return [
        BlockedRead(
            id=b.id,
            kind=b.kind,
            reason=b.reason,
            source_user=people.brief(b.source_user_id),
            created_at=b.created_at,
            created_by_name=people.name(b.created_by_id),
        )
        for b in rows
    ]


async def list_blocked(
    session: AsyncSession, params: PageParams, q: str | None
) -> tuple[list[BlockedRead], int]:
    stmt = select(BlockedIdentifier)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.outerjoin(User, User.id == BlockedIdentifier.source_user_id).where(
            or_(
                User.full_name.ilike(like),
                User.email.ilike(like),
                BlockedIdentifier.reason.ilike(like),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(
        await session.scalars(
            stmt.order_by(BlockedIdentifier.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
        )
    )
    return await blocked_reads(session, rows), int(total or 0)


async def summary(session: AsyncSession) -> RiskSummary:
    counts = dict(
        (
            await session.execute(
                select(RiskSignal.kind, func.count())
                .where(RiskSignal.status == SignalStatus.OPEN)
                .group_by(RiskSignal.kind)
            )
        ).all()
    )
    holds, amount = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(RiskHold.amount), 0)).where(
                RiskHold.status == HoldStatus.HELD
            )
        )
    ).one()
    return RiskSummary(
        open=[KindCount(kind=k, open=int(counts.get(k, 0))) for k in RiskKind],
        holds=int(holds),
        held_amount=amount,
    )


async def user_detail(session: AsyncSession, user_id: uuid.UUID) -> RiskUserDetail:
    from apps.config.services import get_app_config

    user = await session.get(User, user_id)
    if user is None:
        raise services.UserNotFoundError()
    config = (await get_app_config(session)).risk
    signals = list(
        await session.scalars(
            select(RiskSignal)
            .where(or_(RiskSignal.user_id == user_id, RiskSignal.related_user_id == user_id))
            .order_by(RiskSignal.created_at.desc())
            .limit(50)
        )
    )
    devices = list(
        await session.scalars(
            select(DeviceFingerprint)
            .where(DeviceFingerprint.user_id == user_id)
            .order_by(DeviceFingerprint.last_seen.desc())
            .limit(20)
        )
    )
    shared = (
        await session.execute(
            select(DeviceFingerprint.device_hash, DeviceFingerprint.user_id).where(
                DeviceFingerprint.device_hash.in_([d.device_hash for d in devices]),
                DeviceFingerprint.user_id != user_id,
            )
        )
        if devices
        else None
    )
    others: dict[str, list[uuid.UUID]] = {}
    for device, other in shared.all() if shared is not None else []:
        others.setdefault(device, []).append(other)
    people = await People().load(session, [user_id, *(i for ids in others.values() for i in ids)])
    holds = list(
        await session.scalars(
            select(RiskHold)
            .where(or_(RiskHold.user_id == user_id, RiskHold.sender_id == user_id))
            .order_by(RiskHold.created_at.desc())
            .limit(50)
        )
    )
    me = people.brief(user_id)
    assert me is not None
    return RiskUserDetail(
        user=me,
        frozen=services.frozen(user, config),
        suspended=await moderation.active_suspension(session, user_id) is not None,
        signals=await signal_reads(session, signals),
        devices=[
            DeviceRead(
                id=d.id,
                platform=d.platform,
                model=d.model,
                app_version=d.app_version,
                first_seen=d.first_seen,
                last_seen=d.last_seen,
                other_accounts=[
                    b for i in others.get(d.device_hash, []) if (b := people.brief(i)) is not None
                ],
            )
            for d in devices
        ],
        duplicates=await verification.duplicates(session, user_id),
        holds=await hold_reads(session, holds),
        blocked=await blocked_reads(session, await services.blocked_for(session, user_id)),
    )


async def review(
    session: AsyncSession, admin: User, signal_id: uuid.UUID, status: SignalStatus, note: str | None
) -> RiskSignal:
    """Dismissing stops a signal from counting; confirming keeps it. Either can be changed."""
    from apps.config.services import get_app_config
    from apps.rides.state import utcnow

    signal = await session.get(RiskSignal, signal_id, with_for_update=True)
    if signal is None:
        raise services.SignalNotFoundError()
    signal.status = status
    signal.reviewed_by_id = admin.id
    signal.reviewed_at = utcnow()
    signal.review_note = note
    await session.flush()
    config = (await get_app_config(session)).risk
    await services.refresh_scores(session, [signal.user_id, signal.related_user_id], config)
    return signal
