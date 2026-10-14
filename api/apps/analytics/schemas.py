import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

Money = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")]


# --- Finance -----------------------------------------------------------------------------------


class CountAmount(BaseModel):
    count: int
    amount: Money


class TopUpTotals(BaseModel):
    completed: CountAmount
    completed_auto: CountAmount
    completed_manual: CountAmount
    pending: CountAmount
    unmatched: CountAmount
    rejected: CountAmount


class FeeTotals(BaseModel):
    collected: Money
    pending: Money
    waived_count: int


class AdjustmentTotals(BaseModel):
    credit: Money
    debit: Money


class FinanceDay(BaseModel):
    date: date
    top_ups: Money
    fees: Money
    promo_credits: Money


class FinanceSummary(BaseModel):
    from_: date = Field(serialization_alias="from")
    to: date
    top_ups: TopUpTotals
    fees: FeeTotals
    promo_credits: Money
    adjustments: AdjustmentTotals
    transfers: CountAmount
    wallet_balances: Money
    by_day: list[FinanceDay]


# --- Metrics -----------------------------------------------------------------------------------


class MetricsTotals(BaseModel):
    rides_requested: int
    rides_completed: int
    rides_cancelled_passenger: int
    rides_cancelled_driver: int
    rides_cancelled_admin: int
    rides_no_drivers: int
    completion_rate: float | None
    gmv: Money
    discounts: Money
    avg_fare: Money | None
    avg_distance_m: int | None
    avg_assign_s: int | None
    avg_pickup_s: int | None
    avg_trip_s: int | None
    active_drivers: int
    active_passengers: int
    new_passengers: int
    new_drivers: int
    avg_rating_drivers: float | None
    avg_rating_passengers: float | None


class MetricsDay(BaseModel):
    date: date
    requested: int
    completed: int
    cancelled: int
    no_drivers: int
    gmv: Money
    active_drivers: int


class MetricsHour(BaseModel):
    hour: int
    requested: int
    completed: int


class TopDriver(BaseModel):
    user_id: uuid.UUID
    name: str
    rides: int
    earnings: Money
    rating_avg: float | None


class Metrics(BaseModel):
    from_: date = Field(serialization_alias="from")
    to: date
    area: str | None
    totals: MetricsTotals
    by_day: list[MetricsDay]
    by_hour: list[MetricsHour]
    top_drivers: list[TopDriver]


class Overview(BaseModel):
    online_drivers: int
    rides_in_progress: int
    rides_today: int
    completed_today: int
    gmv_today: Money
    pending_driver_applications: int
    pending_reverifications: int = 0  # doc 12: selfies, renewals and moto changes to review
    documents_expiring_week: int = 0
    pending_top_ups: int
    unmatched_top_ups: int
    open_reports: int
    urgent_reports: int
    overdue_drivers: int
    stale_rates: list[str]
    open_alerts: int = 0  # monitoring alerts not resolved yet (see /admin/system/health)


# --- Product analytics (doc 19) ----------------------------------------------------------------


class FunnelStep(BaseModel):
    step: str
    users: int


class Funnels(BaseModel):
    # Cohorts by the day they signed up / applied (precomputed daily).
    passenger: list[FunnelStep]
    driver: list[FunnelStep]
    # Rides requested in the range: quotes seen in the app -> requests -> matched -> completed.
    rides: list[FunnelStep]
    # People who opened each screen of the driver application in the app.
    onboarding_screens: list[FunnelStep]
    computed_at: datetime | None


class RetentionRow(BaseModel):
    cohort: date
    users: int
    # "1", "2", "4", "8": people who rode again that week; None until the week is over.
    weeks: dict[str, int | None]


class RetentionTable(BaseModel):
    rows: list[RetentionRow]
    # Weighted % per week over the cohorts that can be measured.
    average: dict[str, float | None]


class Retention(BaseModel):
    passenger: RetentionTable
    driver: RetentionTable
    computed_at: datetime | None


class SupplyCell(BaseModel):
    cell: str
    lat: float
    lng: float
    requests: int
    no_drivers: int
    quotes: int
    driver_hours: float


class SupplyHourRow(BaseModel):
    hour: int
    requests: int
    no_drivers: int
    quotes: int
    driver_hours: float


class SupplyDemand(BaseModel):
    cells: list[SupplyCell]
    hours: list[SupplyHourRow]


class PromotionRow(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None
    rides: int
    cost: Money
    cost_per_ride: Money | None
    # Passengers whose first completed ride used this promotion.
    new_passengers: int
    cost_per_new_passenger: Money | None
    returned_30d: int
    # New passengers whose first ride is at least 30 days old (the rest can still come back).
    eligible_30d: int
    retention_30d: float | None


class ValueBucket(BaseModel):
    min: float
    max: float | None
    count: int


class TierDrivers(BaseModel):
    above: Money
    fee: Money
    drivers: int


class DriverEconomics(BaseModel):
    month: date
    drivers: int
    total_earnings: Money
    median_earnings: Money | None
    earnings: list[ValueBucket]
    tiers: list[TierDrivers]
    online_drivers: int
    online_hours: float
    ride_hours: float
    utilization: float | None
    utilization_spread: list[ValueBucket]
