import uuid
from datetime import date
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
    pending_top_ups: int
    unmatched_top_ups: int
    open_reports: int
    urgent_reports: int
    overdue_drivers: int
    stale_rates: list[str]
