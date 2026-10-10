"""Driver stats for "Tus viajes": earnings and completed rides today, yesterday, this week, month.

Earnings follow the business rule (docs/product/business-model.md): fare minus the promo discount of
completed rides. Days, weeks (Monday to Sunday) and months are Caracas calendar periods.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.drivers.models import DriverProfile
from apps.rides.models import Ride, RideStatus
from apps.rides.schemas import DriverStats, FrequentPlace, PassengerStats, PeriodStats, StatsDay
from kuulis.core.calendar import CARACAS_TZ, add_months, days_bounds, local_now, month_start

ZERO = Decimal("0.00")
DAYS = 7
FREQUENT_PLACES = 3


def _period(rows: list[tuple[date, int, Decimal]], first: date, last: date) -> PeriodStats:
    picked = [(n, total) for day, n, total in rows if first <= day <= last]
    return PeriodStats(
        rides=sum(n for n, _ in picked),
        earnings=sum((total for _, total in picked), ZERO),
    )


async def driver_stats(session: AsyncSession, user_id: uuid.UUID) -> DriverStats:
    today = local_now().date()
    month = month_start(today)
    last_month = add_months(month, -1)
    week = today - timedelta(days=today.weekday())
    first = min(last_month, today - timedelta(days=DAYS - 1), week)
    start, end = days_bounds(first, today)

    local_day = func.date(func.timezone(str(CARACAS_TZ), Ride.completed_at))
    result = await session.execute(
        select(local_day, func.count(), func.sum(Ride.fare - Ride.discount))
        .where(
            Ride.driver_id == user_id,
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at >= start,
            Ride.completed_at < end,
        )
        .group_by(local_day)
    )
    rows = [(day, n, Decimal(total or 0).quantize(Decimal("0.01"))) for day, n, total in result]

    total_rides = await session.scalar(
        select(func.count()).where(Ride.driver_id == user_id, Ride.status == RideStatus.COMPLETED)
    )
    rating = await session.scalar(
        select(DriverProfile.rating_avg).where(DriverProfile.user_id == user_id)
    )
    yesterday = today - timedelta(days=1)
    by_day = {day: (n, total) for day, n, total in rows}
    return DriverStats(
        today=_period(rows, today, today),
        yesterday=_period(rows, yesterday, yesterday),
        week=_period(rows, week, today),
        month=_period(rows, month, today),
        last_month=_period(rows, last_month, month - timedelta(days=1)),
        by_day=[
            StatsDay(
                date=day,
                rides=by_day.get(day, (0, ZERO))[0],
                earnings=by_day.get(day, (0, ZERO))[1],
            )
            for day in (today - timedelta(days=offset) for offset in range(DAYS - 1, -1, -1))
        ],
        total_rides=total_rides or 0,
        rating=float(rating) if rating is not None else None,
    )


async def passenger_stats(session: AsyncSession, user_id: uuid.UUID) -> PassengerStats:
    completed = (Ride.passenger_id == user_id, Ride.status == RideStatus.COMPLETED)
    rides, distance, spent = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Ride.distance_m), 0),
                func.coalesce(func.sum(Ride.fare - Ride.discount), 0),
            ).where(*completed)
        )
    ).one()

    # Same address = same place; the coordinates of the latest ride there are good enough.
    visits = func.count().label("visits")
    places = await session.execute(
        select(
            Ride.dropoff_address,
            func.max(Ride.completed_at).label("last"),
            visits,
        )
        .where(*completed, Ride.dropoff_address != "")
        .group_by(Ride.dropoff_address)
        .order_by(visits.desc(), func.max(Ride.completed_at).desc())
        .limit(FREQUENT_PLACES)
    )
    frequent: list[FrequentPlace] = []
    for address, last, count in places:
        lat, lng = (
            await session.execute(
                select(Ride.dropoff_lat, Ride.dropoff_lng)
                .where(*completed, Ride.dropoff_address == address, Ride.completed_at == last)
                .limit(1)
            )
        ).one()
        frequent.append(FrequentPlace(address=address, lat=lat, lng=lng, rides=count))

    return PassengerStats(
        rides=rides,
        distance_m=int(distance),
        spent=Decimal(spent).quantize(Decimal("0.01")),
        frequent_places=frequent,
    )
