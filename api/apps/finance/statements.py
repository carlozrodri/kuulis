"""A driver's monthly statement (doc 17): what they earned according to the app, the tier and fee
that applies, and every kind of wallet movement, with the balance at the start and the end."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.services import get_app_config
from apps.rides.models import Ride, RideStatus
from apps.subscriptions import services as subscriptions
from apps.subscriptions.models import Charge
from apps.subscriptions.schemas import Tier
from apps.wallet.models import EntryKind, Wallet, WalletEntry
from kuulis.core.calendar import add_months, local_now, month_bounds, month_start

ZERO = Decimal("0.00")


@dataclass
class Statement:
    month: date
    months: list[date]
    opening_balance: Decimal
    closing_balance: Decimal
    earned: Decimal  # fare minus promo discount of every completed ride
    counted: Decimal  # what counts for the fee (rides outside the free period)
    trips: int
    tier: Tier | None  # the tier the counted earnings fall in
    fee: Decimal  # charged (closed month) or estimated (current month)
    estimated: bool
    charge: Charge | None
    movements: dict[EntryKind, Decimal] = field(default_factory=dict)


def tier_for(tiers: list[Tier], earnings: Decimal) -> Tier | None:
    found = None
    for tier in sorted(tiers, key=lambda t: t.above):
        if earnings > tier.above:
            found = tier
    return found


async def _balance_before(session: AsyncSession, user_id: uuid.UUID, moment) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0))
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(Wallet.user_id == user_id, WalletEntry.created_at < moment)
    )
    return Decimal(total or 0).quantize(Decimal("0.01"))


async def available_months(session: AsyncSession, user_id: uuid.UUID) -> list[date]:
    """From the first month with a ride or a movement up to this month, newest first."""
    first_entry = await session.scalar(
        select(func.min(WalletEntry.created_at))
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(Wallet.user_id == user_id)
    )
    first_ride = await session.scalar(
        select(func.min(Ride.completed_at)).where(
            Ride.driver_id == user_id, Ride.status == RideStatus.COMPLETED
        )
    )
    current = month_start(local_now())
    starts = [month_start(m) for m in (first_entry, first_ride) if m is not None]
    month = min(starts) if starts else current
    months = []
    while month <= current and len(months) < 120:
        months.append(month)
        month = add_months(month, 1)
    return list(reversed(months))


async def build(session: AsyncSession, user_id: uuid.UUID, month: date) -> Statement:
    from apps.drivers.models import DriverProfile

    month = month_start(month)
    start, end = month_bounds(month)
    config = await get_app_config(session)
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id))
    rides = (
        await session.execute(
            select(
                func.count(Ride.id), func.coalesce(func.sum(Ride.fare - Ride.discount), 0)
            ).where(
                Ride.driver_id == user_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= start,
                Ride.completed_at < end,
            )
        )
    ).one()
    charge = await session.scalar(
        select(Charge).where(Charge.user_id == user_id, Charge.month == month)
    )
    schedule = await subscriptions.schedule_for(session, month)
    if charge is not None:
        counted, fee, estimated = charge.earnings, charge.fee, False
    else:
        counted = (
            (await subscriptions.month_earnings(session, profile, month, config))[0]
            if profile
            else ZERO
        )
        fee, estimated = subscriptions.fee_for(schedule.tiers, counted), True
    movements = {
        kind: Decimal(total or 0).quantize(Decimal("0.01"))
        for kind, total in await session.execute(
            select(WalletEntry.kind, func.sum(WalletEntry.amount))
            .join(Wallet, Wallet.id == WalletEntry.wallet_id)
            .where(
                Wallet.user_id == user_id,
                WalletEntry.created_at >= start,
                WalletEntry.created_at < end,
            )
            .group_by(WalletEntry.kind)
        )
    }
    return Statement(
        month=month,
        months=await available_months(session, user_id),
        opening_balance=await _balance_before(session, user_id, start),
        closing_balance=await _balance_before(session, user_id, end),
        earned=Decimal(rides[1] or 0).quantize(Decimal("0.01")),
        counted=counted,
        trips=int(rides[0] or 0),
        tier=tier_for(schedule.tiers, counted),
        fee=fee,
        estimated=estimated,
        charge=charge,
        movements={kind: movements.get(kind, ZERO) for kind in EntryKind},
    )
