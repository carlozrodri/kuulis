"""Calendar months in Caracas time (fees, transfer limits and earnings are per local month)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CARACAS_TZ = ZoneInfo("America/Caracas")


def local_now() -> datetime:
    return datetime.now(UTC).astimezone(CARACAS_TZ)


def month_start(value: date | datetime) -> date:
    if isinstance(value, datetime):
        value = value.astimezone(CARACAS_TZ).date()
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    """Same day ``months`` later, clamped to the end of the month (Jan 31 + 1 = Feb 28/29)."""
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    for day in (value.day, 30, 29, 28):
        try:
            return value.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    raise ValueError(value)


def add_months_dt(value: datetime, months: int) -> datetime:
    local = value.astimezone(CARACAS_TZ)
    moved = add_months(local.date(), months)
    return datetime.combine(moved, local.timetz()).astimezone(UTC)


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """[start, end) of a local month as UTC datetimes."""
    start = datetime.combine(month.replace(day=1), time(0), tzinfo=CARACAS_TZ)
    end = datetime.combine(add_months(month.replace(day=1), 1), time(0), tzinfo=CARACAS_TZ)
    return start.astimezone(UTC), end.astimezone(UTC)


def parse_month(value: str) -> date:
    """ "2026-10" -> date(2026, 10, 1)."""
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except ValueError as exc:
        raise ValueError("expected YYYY-MM") from exc


def format_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def days_bounds(first: date, last: date) -> tuple[datetime, datetime]:
    """[start of ``first``, start of the day after ``last``) in Caracas, as UTC datetimes."""
    start = datetime.combine(first, time(0), tzinfo=CARACAS_TZ)
    end = datetime.combine(last + timedelta(days=1), time(0), tzinfo=CARACAS_TZ)
    return start.astimezone(UTC), end.astimezone(UTC)
