from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Status = Literal["ok", "warning", "down", "off"]


class ServiceHealth(BaseModel):
    name: str
    status: Status  # off: not configured
    latency_ms: float | None = None


class LoopHealth(BaseModel):
    name: str
    status: Status  # warning: late but within twice the limit
    last_beat_at: datetime | None
    max_age_seconds: int


class Queues(BaseModel):
    taskiq_pending: int | None  # None when the queue cannot be read
    dispatch_due: int
    dispatch_overdue: int


class Traffic(BaseModel):
    requests_5m: int
    errors_5m: int
    error_rate_5m: float
    avg_ms_5m: float


class RidesHealth(BaseModel):
    searching: int
    requested_last_hour: int
    no_drivers_last_hour: int


class BackupsHealth(BaseModel):
    configured: bool
    last_backup_at: datetime | None = None
    last_backup_bytes: int | None = None
    last_ledger_at: datetime | None = None
    last_files_mirror_at: datetime | None = None
    last_restore_check_at: datetime | None = None
    last_restore_ok: bool | None = None
    errors: dict[str, str] = {}  # job -> last error, while it keeps failing


class OpenAlert(BaseModel):
    key: str
    message: str
    since: datetime


class SystemHealth(BaseModel):
    env: str
    commit: str | None
    checked_at: datetime
    services: list[ServiceHealth]
    loops: list[LoopHealth]
    queues: Queues
    traffic: Traffic
    rides: RidesHealth
    stale_rates: list[str]
    disk_used_percent: float | None
    backups: BackupsHealth
    alerts: list[OpenAlert]
