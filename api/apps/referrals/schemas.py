import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from apps.config.schemas import ReferralProgram
from apps.referrals.models import ReferralStatus, RewardKind
from apps.subscriptions.schemas import MoneyStr, UserBrief

Money = Annotated[Decimal, MoneyStr]


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class ProgramInfo(BaseModel):
    """What the app and the web explain: the reward and how to earn it."""

    active: bool  # new codes are accepted
    reward_usd: Money
    required_trips: int
    window_days: int
    referred_free_month: bool
    ends_at: datetime | None


class Invitee(BaseModel):
    """A driver who joined with the code, as the inviter sees them (never the fraud reason)."""

    name: str  # "Luis G."
    joined_at: datetime
    approved: bool
    # pending (on the way), reviewing (met the trips, the reward waits), rewarded, expired,
    # not_eligible.
    status: Literal["pending", "reviewing", "rewarded", "expired", "not_eligible"]
    trips: int  # counted trips, at most required_trips
    required_trips: int
    deadline_at: datetime | None  # null until approved
    reward_usd: Money | None
    reward_kind: RewardKind | None


class ReferralSummary(BaseModel):
    """GET /referrals/me."""

    # Null until the user is an approved driver (only drivers can invite).
    code: str | None
    share_url: str | None  # the web invite page, https://<site>/i/CODE
    invited: int  # drivers who joined with the code
    rewarded: int  # of those, the ones that earned a reward
    earned_usd: Money  # wallet credit earned with invites
    # Months of subscription this driver has earned and not used yet.
    free_months: int
    # Who invited this user (first name and initial), if anyone.
    referred_by: str | None
    # True while this user can still enter an invite code (a driver before their first trip).
    can_redeem: bool
    program: ProgramInfo
    invitees: list[Invitee]  # newest first, at most 50


class PublicCode(BaseModel):
    """GET /referrals/codes/{code} (no account): the web invite page."""

    code: str
    name: str | None  # first name of who invites
    program: ProgramInfo


# --- Admin -------------------------------------------------------------------------------------


class ReferralAdminRead(BaseModel):
    id: uuid.UUID
    code: str
    status: ReferralStatus
    referrer: UserBrief | None
    referred: UserBrief | None
    trips: int
    required_trips: int
    deadline_at: datetime | None
    qualified_at: datetime | None
    rewarded_at: datetime | None
    reward_kind: RewardKind | None
    reward_amount: Money | None
    # monthly_cap, budget, program_off, risk_score, expired, shared_identity, inviter_inactive,
    # staff
    reason: str | None
    details: dict[str, Any]
    note: str | None
    reviewed_at: datetime | None
    created_at: datetime


class StatusCount(BaseModel):
    status: ReferralStatus
    count: int


class ReferralsOverview(BaseModel):
    program: ReferralProgram
    counts: list[StatusCount]
    paid_usd: Money
    held_usd: Money
    month_paid_usd: Money
    budget_left_usd: Money  # budget - paid - held
    free_months: int  # rewards of the first version (a free month per first trip)
    alerts: int  # held rewards plus unreviewed shared-identity rejections
    waiting: dict[str, int]  # qualified referrals by reason (monthly_cap, budget, program_off)


class RankingRow(BaseModel):
    user: UserBrief | None
    invited: int
    rewarded: int
    earned_usd: Money


class ReviewWrite(BaseModel):
    note: str | None = Field(default=None, max_length=500)
