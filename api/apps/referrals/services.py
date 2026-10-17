"""Driver referrals (doc 22). An approved driver shares a code; a new driver enters it before
their first trip. When the invited driver completes ``required_trips`` within ``window_days`` of
being approved, the inviter earns ``reward_usd`` as ``referral_bonus`` wallet credit
(``AppConfig.referral_program``).

Every evaluation goes through ``evaluate``: on approval, after each completed trip (a queued
task) and in the hourly sweep, which expires late referrals and retries the ones waiting for a
monthly cap or the budget. Anti-fraud: no reward when both accounts share an identity mark (phone,
device, Binance Pay ID, cédula...), trips with the inviter as passenger or flagged as suspicious
do not count, and a high risk score holds the reward for a person.

Before doc 22 the reward was a free month for the invited driver's first trip; those rows keep
``reward_kind = free_month`` and the months already earned are still used by subscriptions.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, and_, case, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.config.schemas import AppConfig, ReferralProgram
from apps.drivers.models import DriverProfile, DriverStatus, IdentityMark
from apps.referrals.models import Referral, ReferralStatus, RewardKind
from apps.referrals.schemas import (
    Invitee,
    ProgramInfo,
    PublicCode,
    RankingRow,
    ReferralAdminRead,
    ReferralsOverview,
    ReferralSummary,
    StatusCount,
)
from apps.rides.models import Ride, RideStatus
from apps.risk.models import RiskKind, RiskSignal, SignalStatus
from apps.subscriptions.schemas import UserBrief
from apps.users.models import User
from apps.wallet import notify
from apps.wallet.models import EntryKind
from kuulis.core.calendar import local_now, month_bounds, month_start
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from kuulis.core.pagination import PageParams
from kuulis.settings import settings

logger = logging.getLogger(__name__)

# No 0/O, 1/I/L: codes are read aloud and typed by hand.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6
ZERO = Decimal("0.00")
# Serializes the budget check across workers (pg_advisory_xact_lock key).
BUDGET_LOCK = 22_022
OPEN_STATUSES = (ReferralStatus.PENDING, ReferralStatus.QUALIFIED)
# Rewards that count against the budget and the monthly cap.
SPENT_STATUSES = (ReferralStatus.REWARDED, ReferralStatus.HELD)
# Rejections the admin lists as alerts (possible abuse), besides held rewards.
ALERT_REASONS = ("shared_identity",)

TEMPLATES = {
    "referral_rewarded": {
        "es": (
            "¡Ganaste {amount} USDT!",
            "{name} completó sus viajes con tu código. Te acreditamos {amount} USDT en tu "
            "billetera.",
        ),
        "en": (
            "You earned {amount} USDT!",
            "{name} completed their rides with your code. We added {amount} USDT to your wallet.",
        ),
    },
    "referral_held": {
        "es": (
            "Tu premio está en revisión",
            "{name} completó sus viajes con tu código. Revisamos el premio de {amount} USDT "
            "antes de acreditarlo.",
        ),
        "en": (
            "Your reward is under review",
            "{name} completed their rides with your code. We are reviewing the {amount} USDT "
            "reward before adding it.",
        ),
    },
    "referral_voided": {
        "es": (
            "Premio por invitación no acreditado",
            "Revisamos la invitación de {name} y no cumple las condiciones del programa.",
        ),
        "en": (
            "Invite reward not paid",
            "We reviewed {name}'s invite and it does not meet the program's conditions.",
        ),
    },
    "referral_free_month": {
        "es": (
            "¡Ganaste un mes gratis!",
            "Completaste tus primeros viajes en Kuulis. Tu próxima cuota corre por nuestra cuenta.",
        ),
        "en": (
            "You earned a free month!",
            "You completed your first rides on Kuulis. Your next fee is on us.",
        ),
    },
}


class InvalidCodeError(AppError):
    code = "referral_code_invalid"
    message = "Invite code not found"


class UnknownCodeError(NotFoundError):
    """The web page of a code that does not exist (404, same code as when redeeming)."""

    code = "referral_code_invalid"
    message = "Invite code not found"


class OwnCodeError(AppError):
    code = "referral_own_code"
    message = "You can't use your own code"


class AlreadyReferredError(ConflictError):
    code = "referral_already_used"
    message = "You already entered an invite code"


class RedeemClosedError(ConflictError):
    code = "referral_closed"
    message = "Invite codes can only be entered before your first trip"


class ProgramClosedError(ConflictError):
    code = "referral_program_closed"
    message = "The invite program is not accepting codes right now"


class NotDriverError(PermissionDeniedError):
    code = "referral_driver_only"
    message = "Only drivers can use invite codes"


class ReferralNotFoundError(NotFoundError):
    code = "referral_not_found"
    message = "Referral not found"


class ReferralInvalidStatusError(ConflictError):
    code = "referral_invalid_status"
    message = "The referral cannot do that in its current status"


class BudgetExhaustedError(ConflictError):
    code = "referral_budget_exhausted"
    message = "The program budget is used up; raise it first"


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def short_name(user: User | None) -> str:
    if user is None:
        return ""
    parts = (user.full_name or "").split()
    if not parts:
        return ""
    return f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else parts[0]


def share_url(code: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/i/{code}"


def _brief(user: User | None) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, name=user.full_name or "", email=user.email)


async def _profile(session: AsyncSession, user_id: uuid.UUID) -> DriverProfile | None:
    return await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id))


def _program_info(program: ReferralProgram, now: datetime) -> ProgramInfo:
    return ProgramInfo(
        active=program.accepting(now),
        reward_usd=program.reward_usd,
        required_trips=program.required_trips,
        window_days=program.window_days,
        referred_free_month=program.referred_free_month,
        ends_at=program.ends_at,
    )


# --- The driver's side -------------------------------------------------------------------------


async def ensure_code(session: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    for _ in range(10):
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))
        taken = await session.scalar(select(User.id).where(User.referral_code == candidate))
        if taken is None:
            user.referral_code = candidate
            await session.flush()
            return candidate
    raise RuntimeError("Could not generate a unique referral code")


def _outcome(referral: Referral) -> str:
    """What the inviter sees: never the anti-fraud reason."""
    if referral.status == ReferralStatus.REJECTED:
        return "expired" if referral.reason == "expired" else "not_eligible"
    if referral.status in (ReferralStatus.QUALIFIED, ReferralStatus.HELD):
        return "reviewing"
    return referral.status.value


async def summary(session: AsyncSession, user: User, config: AppConfig) -> ReferralSummary:
    program = config.referral_program
    now = utcnow()
    profile = await _profile(session, user.id)
    approved = profile is not None and profile.status in (
        DriverStatus.APPROVED,
        DriverStatus.SUSPENDED,
    )
    code = await ensure_code(session, user) if approved else user.referral_code
    rows = list(
        (
            await session.execute(
                select(Referral, User, DriverProfile.status)
                .join(User, User.id == Referral.referred_id)
                .outerjoin(DriverProfile, DriverProfile.user_id == Referral.referred_id)
                .where(Referral.referrer_id == user.id)
                .order_by(Referral.created_at.desc())
            )
        ).all()
    )
    rewarded = [r for r, _, _ in rows if r.status == ReferralStatus.REWARDED]
    earned = sum(
        (r.reward_amount or ZERO for r in rewarded if r.reward_kind == RewardKind.WALLET_CREDIT),
        ZERO,
    )
    mine = await session.scalar(select(Referral).where(Referral.referred_id == user.id))
    referred_by = None
    if mine is not None:
        referred_by = short_name(await session.get(User, mine.referrer_id)) or None
    invitees = [
        Invitee(
            name=short_name(person) or person.email.split("@")[0],
            joined_at=referral.created_at,
            approved=status in (DriverStatus.APPROVED, DriverStatus.SUSPENDED),
            status=_outcome(referral),
            trips=min(referral.trips, program.required_trips),
            required_trips=program.required_trips,
            deadline_at=referral.deadline_at,
            reward_usd=referral.reward_amount,
            reward_kind=referral.reward_kind,
        )
        for referral, person, status in rows[:50]
    ]
    return ReferralSummary(
        code=code,
        share_url=share_url(code) if code else None,
        invited=len(rows),
        rewarded=len(rewarded),
        earned_usd=earned,
        free_months=profile.free_months_credit if profile else 0,
        referred_by=referred_by,
        can_redeem=(
            mine is None
            and profile is not None
            and profile.first_trip_completed_at is None
            and program.accepting(now)
        ),
        program=_program_info(program, now),
        invitees=invitees,
    )


async def redeem(session: AsyncSession, user: User, raw_code: str, config: AppConfig) -> None:
    code = normalize(raw_code)
    profile = await _profile(session, user.id)
    if profile is None:
        raise NotDriverError()
    if profile.first_trip_completed_at is not None:
        raise RedeemClosedError()
    if not config.referral_program.accepting(utcnow()):
        raise ProgramClosedError()
    referrer = await session.scalar(select(User).where(User.referral_code == code))
    if referrer is None or not referrer.is_active:
        raise InvalidCodeError()
    if referrer.id == user.id:
        raise OwnCodeError()
    session.add(Referral(referrer_id=referrer.id, referred_id=user.id, code=code))
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AlreadyReferredError() from exc


async def public_code(session: AsyncSession, raw_code: str, config: AppConfig) -> PublicCode:
    """The web invite page (``/i/{code}``): who invites and what the program offers."""
    code = normalize(raw_code)
    referrer = (
        await session.scalar(select(User).where(User.referral_code == code))
        if len(code) == CODE_LENGTH
        else None
    )
    if referrer is None or not referrer.is_active:
        raise UnknownCodeError()
    return PublicCode(
        code=code,
        name=short_name(referrer).split(" ")[0] or None,
        program=_program_info(config.referral_program, utcnow()),
    )


# --- Evaluation --------------------------------------------------------------------------------


async def shared_marks(session: AsyncSession, one: uuid.UUID, other: uuid.UUID) -> list[str]:
    """Identity kinds (phone, device, binance_pay_id, national_id...) both accounts have used."""
    theirs = aliased(IdentityMark)
    kinds = await session.scalars(
        select(IdentityMark.kind)
        .join(
            theirs,
            and_(theirs.kind == IdentityMark.kind, theirs.value_hash == IdentityMark.value_hash),
        )
        .where(IdentityMark.user_id == one, theirs.user_id == other)
        .distinct()
    )
    return sorted(k.value for k in kinds)


async def counted_trips(session: AsyncSession, referral: Referral) -> int:
    """Completed trips of the invited driver up to the deadline, without the inviter as passenger
    and without the ones flagged as suspicious (open or confirmed)."""
    flagged = select(RiskSignal.ride_id).where(
        RiskSignal.kind == RiskKind.SUSPICIOUS_RIDE,
        RiskSignal.status != SignalStatus.DISMISSED,
        RiskSignal.ride_id.is_not(None),
    )
    stmt = select(func.count(Ride.id)).where(
        Ride.driver_id == referral.referred_id,
        Ride.status == RideStatus.COMPLETED,
        Ride.passenger_id != referral.referrer_id,
        Ride.id.not_in(flagged),
    )
    if referral.deadline_at is not None:
        stmt = stmt.where(Ride.completed_at <= referral.deadline_at)
    return int(await session.scalar(stmt) or 0)


async def _spent(session: AsyncSession) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(Referral.reward_amount), 0)).where(
            Referral.status.in_(SPENT_STATUSES),
            Referral.reward_kind == RewardKind.WALLET_CREDIT,
        )
    )
    return Decimal(total or 0).quantize(Decimal("0.01"))


async def _rewards_this_month(session: AsyncSession, referrer_id: uuid.UUID) -> int:
    start, end = month_bounds(month_start(local_now()))
    when = func.coalesce(Referral.rewarded_at, Referral.qualified_at)
    return int(
        await session.scalar(
            select(func.count(Referral.id)).where(
                Referral.referrer_id == referrer_id,
                Referral.status.in_(SPENT_STATUSES),
                Referral.reward_kind == RewardKind.WALLET_CREDIT,
                when >= start,
                when < end,
            )
        )
        or 0
    )


async def _reserve_budget(session: AsyncSession, program: ReferralProgram) -> bool:
    """Locks the budget until the transaction ends; True when one more reward fits."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BUDGET_LOCK})
    return await _spent(session) + program.reward_usd <= program.budget_usd


async def _pay(session: AsyncSession, referral: Referral, amount: Decimal) -> None:
    from apps.wallet import services as wallet

    referred = await session.get(User, referral.referred_id)
    entry = await wallet.credit(
        session,
        referral.referrer_id,
        EntryKind.REFERRAL_BONUS,
        amount,
        description="Premio por invitar a un motorizado",
        details={"counterpart_name": short_name(referred), "referral_id": str(referral.id)},
    )
    referral.status = ReferralStatus.REWARDED
    referral.rewarded_at = utcnow()
    referral.reward_kind = RewardKind.WALLET_CREDIT
    referral.reward_amount = amount
    referral.reward_entry_id = entry.id
    referral.reason = None
    await notify.send(
        session,
        referral.referrer_id,
        "referral_rewarded",
        kind="referral",
        templates=TEMPLATES,
        name=short_name(referred) or "Tu invitado",
        amount=f"{amount:.2f}",
    )


async def _grant_free_month(session: AsyncSession, referral: Referral, config: AppConfig) -> None:
    """The invited driver's own month (``referred_free_month``), once per referral."""
    if not config.referral_program.referred_free_month or referral.details.get("free_month"):
        return
    await session.execute(
        update(DriverProfile)
        .where(DriverProfile.user_id == referral.referred_id)
        .values(free_months_credit=DriverProfile.free_months_credit + 1)
    )
    referral.details = referral.details | {"free_month": True}
    await notify.send(
        session, referral.referred_id, "referral_free_month", kind="referral", templates=TEMPLATES
    )


async def _flag_shared(
    session: AsyncSession, referral: Referral, kinds: list[str], config: AppConfig
) -> None:
    from apps.risk import services as risk

    referral.status = ReferralStatus.REJECTED
    referral.reason = "shared_identity"
    referral.details = referral.details | {"shared": kinds}
    await risk.raise_signal(
        session,
        user_id=referral.referred_id,
        related_user_id=referral.referrer_id,
        kind=RiskKind.REFERRAL,
        reasons=["shared_identity"],
        dedupe_key=f"referral:{referral.id}",
        config=config.risk,
        evidence={"shared": kinds, "referral_id": str(referral.id)},
    )


def _approved_at(profile: DriverProfile | None) -> datetime | None:
    if profile is None:
        return None
    if profile.approved_at is not None:
        return profile.approved_at
    if profile.status in (DriverStatus.APPROVED, DriverStatus.SUSPENDED):
        return profile.reviewed_at or profile.created_at  # approved before approved_at existed
    return None


async def evaluate(
    session: AsyncSession, referral: Referral, config: AppConfig, now: datetime | None = None
) -> None:
    """Moves an open referral forward: progress, expiry, fraud checks and the reward. The caller
    holds the row lock and commits."""
    if referral.status not in OPEN_STATUSES:
        return
    now = now or utcnow()
    program = config.referral_program
    profile = await _profile(session, referral.referred_id)
    approved_at = _approved_at(profile)
    if approved_at is None:
        return  # not approved yet: the window has not started
    if referral.deadline_at is None:
        referral.deadline_at = approved_at + timedelta(days=program.window_days)
    inviter = await session.get(User, referral.referrer_id)
    if inviter is None or not inviter.is_active or inviter.deleted_at is not None:
        referral.status, referral.reason = ReferralStatus.REJECTED, "inviter_inactive"
        return
    if not referral.details.get("override"):
        kinds = await shared_marks(session, referral.referrer_id, referral.referred_id)
        if kinds:
            await _flag_shared(session, referral, kinds, config)
            return
    referral.trips = await counted_trips(session, referral)
    if referral.trips < program.required_trips:
        if now > referral.deadline_at:
            referral.status, referral.reason = ReferralStatus.REJECTED, "expired"
        return
    if referral.status == ReferralStatus.PENDING:
        referral.status = ReferralStatus.QUALIFIED
        referral.qualified_at = now
        await _grant_free_month(session, referral, config)
    if not program.enabled:
        referral.reason = "program_off"
        return
    if program.monthly_cap and (
        await _rewards_this_month(session, referral.referrer_id) >= program.monthly_cap
    ):
        referral.reason = "monthly_cap"
        return
    if not await _reserve_budget(session, program):
        referral.reason = "budget"
        return
    users = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_([referral.referrer_id, referral.referred_id]))
        )
    }
    scores = {str(uid): u.risk_score for uid, u in users.items()}
    if any(u.risk_score >= config.risk.freeze_score for u in users.values()):
        referral.status = ReferralStatus.HELD
        referral.reason = "risk_score"
        referral.reward_kind = RewardKind.WALLET_CREDIT
        referral.reward_amount = program.reward_usd
        referral.details = referral.details | {"risk_scores": scores}
        await notify.send(
            session,
            referral.referrer_id,
            "referral_held",
            kind="referral",
            templates=TEMPLATES,
            name=short_name(users.get(referral.referred_id)) or "Tu invitado",
            amount=f"{program.reward_usd:.2f}",
        )
        return
    await _pay(session, referral, program.reward_usd)


async def _locked(session: AsyncSession, referral_id: uuid.UUID) -> Referral:
    referral = await session.get(Referral, referral_id, with_for_update=True)
    if referral is None:
        raise ReferralNotFoundError()
    return referral


async def evaluate_driver(session: AsyncSession, driver_id: uuid.UUID) -> ReferralStatus | None:
    """After an approval or a completed trip of ``driver_id``. Commits."""
    from apps.config.services import get_app_config

    referral_id = await session.scalar(
        select(Referral.id).where(
            Referral.referred_id == driver_id, Referral.status.in_(OPEN_STATUSES)
        )
    )
    if referral_id is None:
        return None
    referral = await _locked(session, referral_id)
    await evaluate(session, referral, await get_app_config(session))
    await session.commit()
    return referral.status


async def sweep(session: AsyncSession, config: AppConfig) -> dict[str, int]:
    """Every open referral of an approved driver: expires the late ones and pays the ones that
    were waiting (a new month, a bigger budget, the program turned back on)."""
    ids = list(
        await session.scalars(
            select(Referral.id)
            .join(DriverProfile, DriverProfile.user_id == Referral.referred_id)
            .where(
                Referral.status.in_(OPEN_STATUSES),
                or_(
                    DriverProfile.approved_at.is_not(None),
                    DriverProfile.status.in_([DriverStatus.APPROVED, DriverStatus.SUSPENDED]),
                ),
            )
            .order_by(Referral.created_at)
        )
    )
    result: dict[str, int] = {}
    now = utcnow()
    for referral_id in ids:
        try:
            referral = await _locked(session, referral_id)
            before = referral.status
            await evaluate(session, referral, config, now)
            await session.commit()
            if referral.status != before:
                result[referral.status.value] = result.get(referral.status.value, 0) + 1
        except Exception:
            await session.rollback()
            logger.exception("Could not evaluate referral %s", referral_id)
    return result


# --- Admin -------------------------------------------------------------------------------------


def _admin_stmt(
    status: ReferralStatus | None, alerts: bool, q: str | None, referrer_id: uuid.UUID | None
) -> tuple[Select, type[User], type[User]]:
    referrer, referred = aliased(User), aliased(User)
    stmt = (
        select(Referral, referrer, referred)
        .join(referrer, referrer.id == Referral.referrer_id)
        .join(referred, referred.id == Referral.referred_id)
        .order_by(Referral.created_at.desc(), Referral.id)
    )
    if status is not None:
        stmt = stmt.where(Referral.status == status)
    if alerts:
        stmt = stmt.where(
            or_(
                Referral.status == ReferralStatus.HELD,
                and_(
                    Referral.status == ReferralStatus.REJECTED,
                    Referral.reason.in_(ALERT_REASONS),
                    Referral.reviewed_at.is_(None),
                ),
            )
        )
    if referrer_id is not None:
        stmt = stmt.where(
            or_(Referral.referrer_id == referrer_id, Referral.referred_id == referrer_id)
        )
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(referrer.full_name).like(like),
                func.lower(referrer.email).like(like),
                func.lower(referred.full_name).like(like),
                func.lower(referred.email).like(like),
                Referral.code == normalize(q),
            )
        )
    return stmt, referrer, referred


def admin_read(
    referral: Referral, referrer: User | None, referred: User | None, required: int
) -> ReferralAdminRead:
    return ReferralAdminRead(
        id=referral.id,
        code=referral.code,
        status=referral.status,
        referrer=_brief(referrer),
        referred=_brief(referred),
        trips=referral.trips,
        required_trips=required,
        deadline_at=referral.deadline_at,
        qualified_at=referral.qualified_at,
        rewarded_at=referral.rewarded_at,
        reward_kind=referral.reward_kind,
        reward_amount=referral.reward_amount,
        reason=referral.reason,
        details=referral.details,
        note=referral.note,
        reviewed_at=referral.reviewed_at,
        created_at=referral.created_at,
    )


async def list_referrals(
    session: AsyncSession,
    params: PageParams,
    config: AppConfig,
    *,
    status: ReferralStatus | None = None,
    alerts: bool = False,
    q: str | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[list[ReferralAdminRead], int]:
    stmt, _, _ = _admin_stmt(status, alerts, q, user_id)
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (await session.execute(stmt.limit(params.limit).offset(params.offset))).all()
    required = config.referral_program.required_trips
    return [admin_read(r, a, b, required) for r, a, b in rows], int(total or 0)


async def get_admin(
    session: AsyncSession, referral_id: uuid.UUID, config: AppConfig
) -> ReferralAdminRead:
    referral = await session.get(Referral, referral_id)
    if referral is None:
        raise ReferralNotFoundError()
    return admin_read(
        referral,
        await session.get(User, referral.referrer_id),
        await session.get(User, referral.referred_id),
        config.referral_program.required_trips,
    )


async def overview(session: AsyncSession, config: AppConfig) -> ReferralsOverview:
    program = config.referral_program
    counts = dict(
        (
            await session.execute(
                select(Referral.status, func.count(Referral.id)).group_by(Referral.status)
            )
        ).all()
    )
    paid, held = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(
                        case((Referral.status == ReferralStatus.REWARDED, Referral.reward_amount))
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case((Referral.status == ReferralStatus.HELD, Referral.reward_amount))
                    ),
                    0,
                ),
            ).where(Referral.reward_kind == RewardKind.WALLET_CREDIT)
        )
    ).one()
    free_months = await session.scalar(
        select(func.count(Referral.id)).where(Referral.reward_kind == RewardKind.FREE_MONTH)
    )
    alerts = await session.scalar(
        select(func.count()).select_from(_admin_stmt(None, True, None, None)[0].subquery())
    )
    start, end = month_bounds(month_start(local_now()))
    month_paid = await session.scalar(
        select(func.coalesce(func.sum(Referral.reward_amount), 0)).where(
            Referral.status == ReferralStatus.REWARDED,
            Referral.reward_kind == RewardKind.WALLET_CREDIT,
            Referral.rewarded_at >= start,
            Referral.rewarded_at < end,
        )
    )
    paid, held = Decimal(paid), Decimal(held)
    waiting = dict(
        (
            await session.execute(
                select(Referral.reason, func.count(Referral.id))
                .where(Referral.status == ReferralStatus.QUALIFIED)
                .group_by(Referral.reason)
            )
        ).all()
    )
    return ReferralsOverview(
        program=program,
        counts=[StatusCount(status=s, count=int(counts.get(s, 0))) for s in ReferralStatus],
        paid_usd=paid,
        held_usd=held,
        month_paid_usd=Decimal(month_paid or 0),
        budget_left_usd=max(ZERO, program.budget_usd - paid - held),
        free_months=int(free_months or 0),
        alerts=int(alerts or 0),
        waiting={str(k or "other"): int(v) for k, v in waiting.items()},
    )


async def ranking(session: AsyncSession, limit: int = 10) -> list[RankingRow]:
    rewarded = func.count(case((Referral.status == ReferralStatus.REWARDED, Referral.id)))
    earned = func.coalesce(
        func.sum(
            case(
                (
                    and_(
                        Referral.status == ReferralStatus.REWARDED,
                        Referral.reward_kind == RewardKind.WALLET_CREDIT,
                    ),
                    Referral.reward_amount,
                )
            )
        ),
        0,
    )
    rows = await session.execute(
        select(User, func.count(Referral.id), rewarded, earned)
        .join(Referral, Referral.referrer_id == User.id)
        .group_by(User.id)
        .order_by(rewarded.desc(), func.count(Referral.id).desc(), User.id)
        .limit(limit)
    )
    return [
        RankingRow(user=_brief(user), invited=invited, rewarded=done, earned_usd=Decimal(total))
        for user, invited, done, total in rows
    ]


def _review(referral: Referral, admin: User, note: str | None) -> None:
    referral.reviewed_by_id = admin.id
    referral.reviewed_at = utcnow()
    referral.note = note


async def release(
    session: AsyncSession,
    admin: User,
    referral_id: uuid.UUID,
    note: str | None,
    config: AppConfig,
) -> Referral:
    """Pays a held reward, or a qualified one waiting for the cap (the budget still applies)."""
    referral = await _locked(session, referral_id)
    if referral.status not in (ReferralStatus.HELD, ReferralStatus.QUALIFIED):
        raise ReferralInvalidStatusError()
    if referral.status == ReferralStatus.QUALIFIED:
        if not await _reserve_budget(session, config.referral_program):
            raise BudgetExhaustedError()
        amount = config.referral_program.reward_usd
    else:
        amount = referral.reward_amount or config.referral_program.reward_usd
    await _pay(session, referral, amount)
    _review(referral, admin, note)
    await session.flush()
    return referral


async def reject(
    session: AsyncSession, admin: User, referral_id: uuid.UUID, note: str | None
) -> Referral:
    """No reward. A shared-identity alert that is already rejected is just marked reviewed."""
    referral = await _locked(session, referral_id)
    if referral.status == ReferralStatus.REWARDED:
        raise ReferralInvalidStatusError()
    if referral.status == ReferralStatus.REJECTED:
        if referral.reviewed_at is not None:
            raise ReferralInvalidStatusError()
    else:
        if referral.status == ReferralStatus.HELD:
            referred = await session.get(User, referral.referred_id)
            await notify.send(
                session,
                referral.referrer_id,
                "referral_voided",
                kind="referral",
                templates=TEMPLATES,
                name=short_name(referred) or "Tu invitado",
            )
        referral.status = ReferralStatus.REJECTED
        referral.reason = "staff"
        referral.reward_amount = None
    _review(referral, admin, note)
    await session.flush()
    return referral


async def reopen(
    session: AsyncSession,
    admin: User,
    referral_id: uuid.UUID,
    note: str | None,
    config: AppConfig,
) -> Referral:
    """A rejection that was wrong (relatives sharing a phone, a late approval): the referral is
    evaluated again, without the shared-identity check."""
    referral = await _locked(session, referral_id)
    if referral.status != ReferralStatus.REJECTED:
        raise ReferralInvalidStatusError()
    referral.status = ReferralStatus.PENDING
    referral.reason = None
    referral.details = referral.details | {"override": True}
    if referral.deadline_at is not None and referral.deadline_at < utcnow():
        # A new window from today, so the reopened invite can still qualify.
        referral.deadline_at = utcnow() + timedelta(days=config.referral_program.window_days)
    _review(referral, admin, note)
    await evaluate(session, referral, config)
    await session.flush()
    return referral
