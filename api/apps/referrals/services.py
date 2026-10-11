"""Driver referrals: an approved driver shares a code; a new driver enters it before their first
trip; when that first trip is completed the inviter earns one free month of subscription (the
next charge with a fee is waived, see ``apps.subscriptions.services.charge_month``)."""

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.drivers.models import DriverProfile, DriverStatus
from apps.referrals.models import Referral
from apps.referrals.schemas import ReferralSummary
from apps.users.models import User
from apps.wallet import notify
from kuulis.core.exceptions import AppError, ConflictError, PermissionDeniedError

# No 0/O, 1/I/L: codes are read aloud and typed by hand.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6

TEMPLATES = {
    "referral_rewarded": {
        "es": (
            "¡Ganaste un mes gratis!",
            "{name} completó su primer viaje con tu código. Tu próxima cuota corre por Kuulis.",
        ),
        "en": (
            "You earned a free month!",
            "{name} completed their first ride with your code. Kuulis covers your next fee.",
        ),
    },
}


class InvalidCodeError(AppError):
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


class NotDriverError(PermissionDeniedError):
    code = "referral_driver_only"
    message = "Only drivers can use invite codes"


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def short_name(user: User) -> str:
    parts = (user.full_name or "").split()
    if not parts:
        return ""
    return f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else parts[0]


async def _profile(session: AsyncSession, user_id: uuid.UUID) -> DriverProfile | None:
    return await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id))


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


async def summary(session: AsyncSession, user: User) -> ReferralSummary:
    profile = await _profile(session, user.id)
    approved = profile is not None and profile.status in (
        DriverStatus.APPROVED,
        DriverStatus.SUSPENDED,
    )
    code = await ensure_code(session, user) if approved else user.referral_code
    invited, rewarded = (
        await session.execute(
            select(func.count(), func.count(Referral.rewarded_at)).where(
                Referral.referrer_id == user.id
            )
        )
    ).one()
    mine = await session.scalar(select(Referral).where(Referral.referred_id == user.id))
    referred_by = None
    if mine is not None:
        referrer = await session.get(User, mine.referrer_id)
        referred_by = short_name(referrer) if referrer else None
    return ReferralSummary(
        code=code,
        invited=invited,
        rewarded=rewarded,
        free_months=profile.free_months_credit if profile else 0,
        referred_by=referred_by,
        can_redeem=mine is None and profile is not None and profile.first_trip_completed_at is None,
    )


async def redeem(session: AsyncSession, user: User, raw_code: str) -> None:
    code = normalize(raw_code)
    profile = await _profile(session, user.id)
    if profile is None:
        raise NotDriverError()
    if profile.first_trip_completed_at is not None:
        raise RedeemClosedError()
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


async def reward_first_trip(session: AsyncSession, driver_id: uuid.UUID) -> uuid.UUID | None:
    """Called in the transaction that set the driver's first trip. Returns the rewarded inviter."""
    referrer_id = await session.scalar(
        update(Referral)
        .where(Referral.referred_id == driver_id, Referral.rewarded_at.is_(None))
        .values(rewarded_at=datetime.now(UTC))
        .returning(Referral.referrer_id)
    )
    if referrer_id is None:
        return None
    await session.execute(
        update(DriverProfile)
        .where(DriverProfile.user_id == referrer_id)
        .values(free_months_credit=DriverProfile.free_months_credit + 1)
    )
    return referrer_id


async def notify_rewarded(session: AsyncSession, referrer_id: uuid.UUID, driver: User) -> None:
    await notify.send(
        session,
        referrer_id,
        "referral_rewarded",
        kind="referral",
        templates=TEMPLATES,
        name=short_name(driver) or driver.email,
    )
    await session.commit()
