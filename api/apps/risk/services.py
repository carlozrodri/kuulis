"""Anti-fraud rules (doc 16).

Signals are raised by simple rules and reviewed by a person; nothing here bans anyone on its own.
What the rules can do without a person: hold a promotion credit or a transfer until it is
reviewed, block outgoing transfers of a high-risk account, take a driver with a simulated
location offline, leave ratings between suspicious pairs out of the averages and refuse a new
account that reuses an identifier of a banned one.
"""

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from itertools import pairwise

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig, RiskSettings
from apps.drivers.models import IdentityMark, MarkKind
from apps.drivers.verification import mark_hash, record_marks
from apps.rides.models import Rating, RatingRole, Ride, RideStatus
from apps.rides.state import utcnow
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
from apps.safety import track
from apps.safety.geo import distance_m
from apps.users.models import Role, User
from kuulis.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

# Rule weights: a signal's score is the sum of its reasons (capped at 100).
WEIGHTS: dict[str, int] = {
    "same_device": 60,
    "little_movement": 30,
    "too_short": 30,
    "same_place": 30,
    "no_track": 15,
    "frequent_pair": 20,
    "shared_device": 30,
    "mocked": 40,
    "jumps": 25,
    "chain": 30,
    "fan_in": 20,
    "new_account": 15,
    "rating_ring": 20,
    "shared_identity": 30,
}
EMAIL = "email"  # blocked identifier kind besides the identity mark kinds


class RegistrationBlockedError(PermissionDeniedError):
    code = "registration_blocked"
    message = "This account cannot be created"


class TransfersFrozenError(PermissionDeniedError):
    code = "transfers_frozen"
    message = "Transfers are paused on this account while we review it"


class MockLocationError(ConflictError):
    code = "mock_location"
    message = "Turn off the simulated location to receive rides"


class SignalNotFoundError(NotFoundError):
    code = "risk_signal_not_found"
    message = "Alert not found"


class HoldNotFoundError(NotFoundError):
    code = "risk_hold_not_found"
    message = "Held payment not found"


class HoldNotHeldError(ConflictError):
    code = "risk_hold_not_held"
    message = "This payment was already released or voided"


class BlockedNotFoundError(NotFoundError):
    code = "blocked_identifier_not_found"
    message = "Blocked identifier not found"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "User not found"


class CannotBanStaffError(ConflictError):
    code = "cannot_ban_staff"
    message = "Staff accounts cannot be banned"


def score_of(reasons: Iterable[str]) -> int:
    return min(100, sum(WEIGHTS.get(r, 10) for r in reasons))


# --- Signals and the risk score ----------------------------------------------------------------


async def raise_signal(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: RiskKind,
    reasons: list[str],
    dedupe_key: str,
    config: RiskSettings,
    related_user_id: uuid.UUID | None = None,
    ride_id: uuid.UUID | None = None,
    evidence: dict | None = None,
) -> uuid.UUID | None:
    """Stores the signal unless one with the same key exists; refreshes the scores it touches.
    The caller commits."""
    signal_id = await session.scalar(
        insert(RiskSignal)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            related_user_id=related_user_id,
            ride_id=ride_id,
            kind=kind,
            reasons=reasons,
            score=score_of(reasons),
            evidence=evidence or {},
            status=SignalStatus.OPEN,
            dedupe_key=dedupe_key[:160],
        )
        .on_conflict_do_nothing(index_elements=[RiskSignal.dedupe_key])
        .returning(RiskSignal.id)
    )
    if signal_id is not None:
        logger.info("Risk signal %s %s for %s", kind, reasons, user_id)
        await refresh_scores(session, [user_id, related_user_id], config)
    return signal_id


async def refresh_scores(
    session: AsyncSession, user_ids: Iterable[uuid.UUID | None], config: RiskSettings
) -> dict[uuid.UUID, int]:
    """Score = signals of the window that were not dismissed, where the person is either side,
    capped at 100. Stored in ``users.risk_score``."""
    ids = list({u for u in user_ids if u is not None})
    if not ids:
        return {}
    since = utcnow() - timedelta(days=config.window_days)
    scores: dict[uuid.UUID, int] = dict.fromkeys(ids, 0)
    for column in (RiskSignal.user_id, RiskSignal.related_user_id):
        rows = await session.execute(
            select(column, func.sum(RiskSignal.score))
            .where(
                column.in_(ids),
                RiskSignal.status != SignalStatus.DISMISSED,
                RiskSignal.created_at >= since,
            )
            .group_by(column)
        )
        for uid, total in rows:
            scores[uid] += int(total or 0)
    for uid, total in scores.items():
        scores[uid] = min(100, total)
        await session.execute(update(User).where(User.id == uid).values(risk_score=scores[uid]))
    return scores


def frozen(user: User | None, config: RiskSettings) -> bool:
    return user is not None and user.risk_score >= config.freeze_score


# --- Devices -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    platform: str = ""
    model: str = ""
    app_version: str = ""

    @classmethod
    def from_headers(cls, headers) -> "DeviceInfo | None":
        device_id = (headers.get("x-device-id") or "").strip()[:100]
        if not device_id:
            return None
        return cls(
            device_id=device_id,
            platform=(headers.get("x-client-platform") or "")[:20],
            model=(headers.get("x-device-model") or "")[:80],
            app_version=(headers.get("x-app-version") or "")[:32],
        )


def device_hash(device_id: str) -> str:
    return mark_hash(MarkKind.DEVICE, device_id)


async def record_device(
    session: AsyncSession, user: User, info: DeviceInfo, config: RiskSettings
) -> bool:
    """Notes the phone of a session (login and refresh). A phone new to this account is also an
    identity mark (doc 12) and may raise "shared device". True when it was new. The caller
    commits."""
    now = utcnow()
    value = device_hash(info.device_id)
    inserted = await session.scalar(
        insert(DeviceFingerprint)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            device_hash=value,
            platform=info.platform,
            model=info.model,
            app_version=info.app_version,
            first_seen=now,
            last_seen=now,
        )
        .on_conflict_do_update(
            constraint="uq_device_fingerprints_user_device",
            set_={
                "last_seen": now,
                "platform": info.platform,
                "model": info.model,
                "app_version": info.app_version,
            },
        )
        .returning(DeviceFingerprint.first_seen == now)
    )
    if not inserted:
        return False
    await record_marks(session, user.id, {MarkKind.DEVICE: info.device_id})
    if user.role in (Role.STAFF, Role.ADMIN) or user.is_test_account:
        return True
    accounts = list(
        await session.scalars(
            select(DeviceFingerprint.user_id)
            .join(User, User.id == DeviceFingerprint.user_id)
            .where(
                DeviceFingerprint.device_hash == value,
                User.role.not_in([Role.STAFF, Role.ADMIN]),
                User.is_test_account.is_(False),
            )
            .order_by(DeviceFingerprint.first_seen)
        )
    )
    if len(accounts) > config.max_accounts_per_device:
        others = [a for a in accounts if a != user.id]
        await raise_signal(
            session,
            user_id=user.id,
            related_user_id=others[0] if others else None,
            kind=RiskKind.SHARED_DEVICE,
            reasons=["shared_device"],
            dedupe_key=f"device:{value[:24]}:{len(accounts)}",
            config=config,
            evidence={
                "accounts": [str(a) for a in accounts],
                "count": len(accounts),
                "platform": info.platform,
                "model": info.model,
            },
        )
    return True


async def device_hashes(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    return set(
        await session.scalars(
            select(DeviceFingerprint.device_hash).where(DeviceFingerprint.user_id == user_id)
        )
    )


# --- Banned identifiers ------------------------------------------------------------------------


async def ensure_not_blocked(session: AsyncSession, values: dict[str, str | None]) -> None:
    """403 ``registration_blocked`` (without saying which) when any value belongs to a banned
    account. ``values`` maps a kind ("email" or a MarkKind value) to the raw value."""
    pairs = [(kind, mark_hash(kind, v)) for kind, v in values.items() if v and v.strip()]
    if not pairs:
        return
    found = await session.scalar(
        select(BlockedIdentifier.id)
        .where(
            or_(
                *(
                    and_(BlockedIdentifier.kind == kind, BlockedIdentifier.value_hash == value)
                    for kind, value in pairs
                )
            )
        )
        .limit(1)
    )
    if found is not None:
        logger.warning("Blocked registration attempt (%s)", ", ".join(k for k, _ in pairs))
        raise RegistrationBlockedError()


async def ban(
    session: AsyncSession, admin: User, user_id: uuid.UUID, reason: str
) -> list[BlockedIdentifier]:
    """Suspends the account with no end date and blocks its email, cédula, RIF, plate, phone,
    Binance Pay ID and phones for new accounts. The caller commits."""
    from apps.moderation import services as moderation

    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    if user.role in (Role.STAFF, Role.ADMIN):
        raise CannotBanStaffError()
    await moderation.suspend(session, admin, user_id, reason, None, None)
    marks = (
        await session.execute(
            select(IdentityMark.kind, IdentityMark.value_hash).where(
                IdentityMark.user_id == user_id
            )
        )
    ).all()
    rows = [(kind.value, value) for kind, value in marks]
    if user.email and user.deleted_at is None:
        rows.append((EMAIL, mark_hash(EMAIL, user.email.lower())))
    for kind, value in rows:
        await session.execute(
            insert(BlockedIdentifier)
            .values(
                id=uuid.uuid4(),
                kind=kind,
                value_hash=value,
                reason=reason[:500],
                source_user_id=user_id,
                created_by_id=admin.id,
            )
            .on_conflict_do_nothing(constraint="uq_blocked_identifiers")
        )
    await session.flush()
    return await blocked_for(session, user_id)


async def blocked_for(session: AsyncSession, user_id: uuid.UUID) -> list[BlockedIdentifier]:
    return list(
        await session.scalars(
            select(BlockedIdentifier)
            .where(BlockedIdentifier.source_user_id == user_id)
            .order_by(BlockedIdentifier.kind)
        )
    )


async def unblock(session: AsyncSession, blocked_id: uuid.UUID) -> BlockedIdentifier:
    row = await session.get(BlockedIdentifier, blocked_id)
    if row is None:
        raise BlockedNotFoundError()
    await session.delete(row)
    return row


# --- Rides -------------------------------------------------------------------------------------


@dataclass
class RideCheck:
    reasons: list[str] = field(default_factory=list)  # ride rules that fired (pair excluded)
    pair_rides: int = 0
    hold: bool = False

    @property
    def score(self) -> int:
        extra = ["frequent_pair"] if self.pair_rides else []
        return score_of(self.reasons + extra)


def path_length(points: list[tuple[float, float, float]]) -> float:
    return sum(distance_m(a[0], a[1], b[0], b[1]) for a, b in pairwise(points))


async def pair_rides(
    session: AsyncSession, passenger_id: uuid.UUID, driver_id: uuid.UUID, days: int
) -> int:
    return int(
        await session.scalar(
            select(func.count()).where(
                Ride.passenger_id == passenger_id,
                Ride.driver_id == driver_id,
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= utcnow() - timedelta(days=days),
            )
        )
        or 0
    )


async def check_ride(session: AsyncSession, ride: Ride, config: AppConfig) -> RideCheck:
    """Runs when a ride completes (before its promotion credit, same transaction). Raises the
    alerts and says whether the promotion credit waits for a review. The caller commits."""
    r = config.risk
    assert ride.driver_id is not None
    result = RideCheck()
    shared = (await device_hashes(session, ride.passenger_id)) & (
        await device_hashes(session, ride.driver_id)
    )
    if shared:
        result.reasons.append("same_device")

    started = ride.started_at or ride.assigned_at or ride.requested_at
    points = [p for p in await track.buffered(ride.id) if p[2] >= started.timestamp() - 5]
    path = path_length(points)
    if ride.distance_m >= r.min_ride_m:
        if len(points) < 2:
            result.reasons.append("no_track")
        else:
            if path < ride.distance_m * r.min_path_share:
                result.reasons.append("little_movement")
            first, last = points[0], points[-1]
            if distance_m(first[0], first[1], last[0], last[1]) < r.same_place_m:
                result.reasons.append("same_place")
    real_s = (ride.completed_at - started).total_seconds() if ride.completed_at else 0
    if ride.duration_s >= 300 and real_s < ride.duration_s * r.min_duration_share:
        result.reasons.append("too_short")

    count = await pair_rides(session, ride.passenger_id, ride.driver_id, r.pair_days)
    if count >= r.pair_rides:
        result.pair_rides = count

    evidence = {
        "distance_m": ride.distance_m,
        "path_m": round(path),
        "estimate_s": ride.duration_s,
        "real_s": round(real_s),
        "points": len(points),
        "pair_rides": count,
        "promotion": ride.discount > 0,
    }
    if result.reasons:
        await raise_signal(
            session,
            user_id=ride.driver_id,
            related_user_id=ride.passenger_id,
            ride_id=ride.id,
            kind=RiskKind.SUSPICIOUS_RIDE,
            reasons=result.reasons + (["frequent_pair"] if result.pair_rides else []),
            dedupe_key=f"ride:{ride.id}",
            config=r,
            evidence=evidence,
        )
    elif result.pair_rides:
        await raise_signal(
            session,
            user_id=ride.driver_id,
            related_user_id=ride.passenger_id,
            ride_id=ride.id,
            kind=RiskKind.FREQUENT_PAIR,
            reasons=["frequent_pair"],
            # Once per pair each time the count reaches another multiple of the threshold.
            dedupe_key=f"pair:{ride.passenger_id}:{ride.driver_id}:{count // r.pair_rides}",
            config=r,
            evidence=evidence | {"days": r.pair_days},
        )
    if ride.discount > 0:
        driver = await session.get(User, ride.driver_id)
        passenger = await session.get(User, ride.passenger_id)
        result.hold = result.score >= r.ride_hold_score or frozen(driver, r) or frozen(passenger, r)
    return result


async def rating_ignored(session: AsyncSession, ride: Ride, config: AppConfig) -> bool:
    """Ratings of a ride whose alert would hold its promotion credit (and was not dismissed), or
    between a frequent pair, do not move the averages."""
    flagged = await session.scalar(
        select(RiskSignal.id)
        .where(
            RiskSignal.ride_id == ride.id,
            RiskSignal.status != SignalStatus.DISMISSED,
            RiskSignal.score >= config.risk.ride_hold_score,
        )
        .limit(1)
    )
    if flagged is not None:
        return True
    assert ride.driver_id is not None
    r = config.risk
    return await pair_rides(session, ride.passenger_id, ride.driver_id, r.pair_days) >= r.pair_rides


# --- Holds -------------------------------------------------------------------------------------


async def hold_promo_credit(session: AsyncSession, ride: Ride, reasons: list[str]) -> RiskHold:
    assert ride.driver_id is not None
    hold = RiskHold(
        kind=HoldKind.PROMO_CREDIT,
        status=HoldStatus.HELD,
        user_id=ride.driver_id,
        amount=ride.discount,
        ride_id=ride.id,
        promotion_id=ride.promotion_id,
        reasons=reasons,
    )
    session.add(hold)
    await session.flush()
    return hold


async def _locked_hold(session: AsyncSession, hold_id: uuid.UUID) -> RiskHold:
    hold = await session.get(RiskHold, hold_id, with_for_update=True)
    if hold is None:
        raise HoldNotFoundError()
    if hold.status != HoldStatus.HELD:
        raise HoldNotHeldError()
    return hold


async def _pay(session: AsyncSession, hold: RiskHold) -> None:
    """Credits the held money to the recipient (and tells them)."""
    from apps.promotions.models import Promotion
    from apps.wallet import notify
    from apps.wallet import services as wallet
    from apps.wallet.models import EntryKind, WalletEntry

    if hold.kind == HoldKind.PROMO_CREDIT:
        promotion = await session.get(Promotion, hold.promotion_id) if hold.promotion_id else None
        await wallet.credit(
            session,
            hold.user_id,
            EntryKind.PROMO_CREDIT,
            hold.amount,
            ride_id=hold.ride_id,
            promotion_id=hold.promotion_id,
            description=promotion.name if promotion else "",
            details={"held": True},
        )
        await notify.send(
            session, hold.user_id, "promo_released", templates=TEMPLATES, amount=_usd(hold.amount)
        )
        return
    entry = await session.get(WalletEntry, hold.entry_id) if hold.entry_id else None
    sender = await session.get(User, hold.sender_id) if hold.sender_id else None
    details = dict(entry.details) if entry else {}
    await wallet.credit(
        session,
        hold.user_id,
        EntryKind.TRANSFER_IN,
        hold.amount,
        counterpart_user_id=hold.sender_id,
        details={
            "counterpart_name": wallet.short_name(sender),
            "note": details.get("note"),
            "held": True,
        },
    )
    if entry is not None:
        entry.details = details | {"held": False, "held_until": None}
    await notify.send(
        session,
        hold.user_id,
        "transfer_received",
        name=wallet.short_name(sender),
        amount=_usd(hold.amount),
    )


async def release(
    session: AsyncSession, admin: User | None, hold_id: uuid.UUID, note: str | None = None
) -> RiskHold:
    """Pays a held promotion credit or transfer. ``admin`` is None for the 24 h release."""
    hold = await _locked_hold(session, hold_id)
    await _pay(session, hold)
    hold.status = HoldStatus.RELEASED
    hold.resolved_at = utcnow()
    hold.resolved_by_id = admin.id if admin else None
    hold.note = note
    await session.flush()
    return hold


async def void(
    session: AsyncSession, admin: User, hold_id: uuid.UUID, note: str | None = None
) -> RiskHold:
    """Does not pay: a promotion credit is dropped, a transfer goes back to its sender."""
    from apps.wallet import notify
    from apps.wallet import services as wallet
    from apps.wallet.models import EntryKind, WalletEntry

    hold = await _locked_hold(session, hold_id)
    if hold.kind == HoldKind.PROMO_CREDIT:
        await notify.send(
            session, hold.user_id, "promo_voided", templates=TEMPLATES, amount=_usd(hold.amount)
        )
    elif hold.sender_id is not None:
        recipient = await session.get(User, hold.user_id)
        await wallet.credit(
            session,
            hold.sender_id,
            EntryKind.TRANSFER_IN,
            hold.amount,
            counterpart_user_id=hold.user_id,
            description="Transferencia devuelta",
            details={"counterpart_name": wallet.short_name(recipient), "returned": True},
        )
        entry = await session.get(WalletEntry, hold.entry_id) if hold.entry_id else None
        if entry is not None:
            entry.details = dict(entry.details) | {"held": False, "returned": True}
        await notify.send(
            session,
            hold.sender_id,
            "transfer_returned",
            templates=TEMPLATES,
            amount=_usd(hold.amount),
            name=wallet.short_name(recipient),
        )
    hold.status = HoldStatus.VOIDED
    hold.resolved_at = utcnow()
    hold.resolved_by_id = admin.id
    hold.note = note
    await session.flush()
    return hold


async def release_due(session: AsyncSession) -> int:
    """First transfers whose waiting time ended (those under review have no ``release_at``)."""
    ids = list(
        await session.scalars(
            select(RiskHold.id)
            .where(
                RiskHold.status == HoldStatus.HELD,
                RiskHold.release_at.is_not(None),
                RiskHold.release_at <= utcnow(),
            )
            .order_by(RiskHold.release_at)
            .limit(200)
        )
    )
    released = 0
    for hold_id in ids:
        try:
            await release(session, None, hold_id)
            await session.commit()
            released += 1
        except HoldNotHeldError:
            await session.rollback()
        except Exception:
            await session.rollback()
            logger.exception("Could not release hold %s", hold_id)
    return released


# --- Transfers ---------------------------------------------------------------------------------


@dataclass
class TransferCheck:
    reasons: list[str] = field(default_factory=list)
    first: bool = False

    @property
    def held(self) -> bool:
        return self.first or bool(self.reasons)


async def check_transfer(
    session: AsyncSession,
    sender: User,
    recipient: User,
    amount: Decimal,
    config: RiskSettings,
) -> TransferCheck:
    """Runs before the money moves. 403 ``transfers_frozen`` for a high-risk sender."""
    from apps.wallet.models import EntryKind, Wallet, WalletEntry

    if frozen(sender, config):
        raise TransfersFrozenError()
    now = utcnow()
    result = TransferCheck()
    sent_before = await session.scalar(
        select(WalletEntry.id)
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(Wallet.user_id == sender.id, WalletEntry.kind == EntryKind.TRANSFER_OUT)
        .limit(1)
    )
    result.first = sent_before is None and config.first_transfer_hold_hours > 0
    received = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0))
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(
            Wallet.user_id == sender.id,
            WalletEntry.kind == EntryKind.TRANSFER_IN,
            # Giving money back to whoever sent it is not passing it on.
            WalletEntry.counterpart_user_id != recipient.id,
            WalletEntry.created_at >= now - timedelta(minutes=config.chain_minutes),
        )
    )
    if Decimal(received or 0) >= amount / 2:
        result.reasons.append("chain")
    senders = await session.scalar(
        select(func.count(func.distinct(WalletEntry.counterpart_user_id)))
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(
            Wallet.user_id == recipient.id,
            WalletEntry.kind == EntryKind.TRANSFER_IN,
            WalletEntry.counterpart_user_id != sender.id,
            WalletEntry.created_at >= now - timedelta(days=7),
        )
    )
    if int(senders or 0) + 1 >= config.fan_in_senders:
        result.reasons.append("fan_in")
    if config.new_account_days and recipient.created_at >= now - timedelta(
        days=config.new_account_days
    ):
        result.reasons.append("new_account")
    if frozen(recipient, config):
        result.reasons.append("recipient_frozen")
    return result


async def hold_transfer(
    session: AsyncSession,
    entry_id: uuid.UUID,
    sender: User,
    recipient: User,
    amount: Decimal,
    check: TransferCheck,
    config: RiskSettings,
) -> RiskHold:
    """The sender's money left; the recipient gets it on release (by time only when nothing but
    "first transfer" applies). The caller commits."""
    reasons = (["first_transfer"] if check.first else []) + check.reasons
    release_at = (
        utcnow() + timedelta(hours=config.first_transfer_hold_hours) if not check.reasons else None
    )
    hold = RiskHold(
        kind=HoldKind.TRANSFER,
        status=HoldStatus.HELD,
        user_id=recipient.id,
        sender_id=sender.id,
        amount=amount,
        entry_id=entry_id,
        reasons=reasons,
        release_at=release_at,
    )
    session.add(hold)
    alerting = [r for r in check.reasons if r in WEIGHTS]
    if alerting:
        # Passing money on is the sender's doing; many senders or a new account, the recipient's.
        user_id = sender.id if "chain" in alerting else recipient.id
        await raise_signal(
            session,
            user_id=user_id,
            kind=RiskKind.TRANSFERS,
            reasons=alerting,
            dedupe_key=f"transfer:{entry_id}",
            config=config,
            evidence={
                "amount": f"{amount:.2f}",
                "sender_id": str(sender.id),
                "recipient_id": str(recipient.id),
                "entry_id": str(entry_id),
            },
        )
    await session.flush()
    return hold


# --- Fake GPS ----------------------------------------------------------------------------------


async def gps_signal(
    session: AsyncSession, user_id: uuid.UUID, reason: str, evidence: dict
) -> uuid.UUID | None:
    """One alert per driver, reason and hour."""
    from apps.config.services import get_app_config

    config = (await get_app_config(session)).risk
    hour = int(utcnow().timestamp() // 3600)
    return await raise_signal(
        session,
        user_id=user_id,
        kind=RiskKind.FAKE_GPS,
        reasons=[reason],
        dedupe_key=f"gps:{user_id}:{reason}:{hour}",
        config=config,
        evidence=evidence,
    )


# --- Sweep -------------------------------------------------------------------------------------


async def rating_rings(session: AsyncSession, config: RiskSettings) -> int:
    """Pairs who gave each other 5 stars on ``rating_ring_rides`` rides or more in 30 days."""
    since = utcnow() - timedelta(days=30)
    five = (
        select(Rating.ride_id, Rating.rater_id, Rating.ratee_id, Rating.rater_role)
        .where(Rating.stars == 5, Rating.created_at >= since)
        .subquery()
    )
    by_passenger = five.alias("p")
    by_driver = five.alias("d")
    rows = (
        await session.execute(
            select(by_driver.c.rater_id, by_passenger.c.rater_id, func.count())
            .select_from(by_passenger)
            .join(
                by_driver,
                and_(
                    by_driver.c.ride_id == by_passenger.c.ride_id,
                    by_driver.c.rater_role == RatingRole.DRIVER,
                ),
            )
            .where(by_passenger.c.rater_role == RatingRole.PASSENGER)
            .group_by(by_driver.c.rater_id, by_passenger.c.rater_id)
            .having(func.count() >= config.rating_ring_rides)
            .limit(500)
        )
    ).all()
    raised = 0
    week = int(utcnow().timestamp() // (7 * 86400))
    for driver_id, passenger_id, count in rows:
        if await raise_signal(
            session,
            user_id=driver_id,
            related_user_id=passenger_id,
            kind=RiskKind.RATING_RING,
            reasons=["rating_ring"],
            dedupe_key=f"ring:{passenger_id}:{driver_id}:{week}",
            config=config,
            evidence={"rides": int(count), "days": 30},
        ):
            raised += 1
    return raised


async def sweep(session: AsyncSession, config: RiskSettings) -> dict[str, int]:
    """Daily: rating rings, and scores refreshed so old signals stop counting."""
    rings = await rating_rings(session, config)
    await session.commit()
    ids = list(await session.scalars(select(User.id).where(User.risk_score > 0)))
    for start in range(0, len(ids), 500):
        await refresh_scores(session, ids[start : start + 500], config)
        await session.commit()
    return {"rating_rings": rings, "scores": len(ids)}


# --- Texts -------------------------------------------------------------------------------------


def _usd(amount: Decimal) -> str:
    return f"{amount:.2f}"


TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "promo_held": {
        "es": (
            "Crédito de promoción en revisión",
            "Revisaremos el viaje antes de sumar {amount} USDT a tu billetera.",
        ),
        "en": (
            "Promotion credit under review",
            "We will review the ride before adding {amount} USDT to your wallet.",
        ),
    },
    "promo_released": {
        "es": ("Crédito de promoción acreditado", "Sumamos {amount} USDT a tu billetera."),
        "en": ("Promotion credit added", "We added {amount} USDT to your wallet."),
    },
    "promo_voided": {
        "es": (
            "Crédito de promoción anulado",
            "Tras revisar el viaje no acreditamos {amount} USDT. Escríbenos si tienes dudas.",
        ),
        "en": (
            "Promotion credit voided",
            "After reviewing the ride we did not add {amount} USDT. Contact us with questions.",
        ),
    },
    "transfer_returned": {
        "es": ("Transferencia devuelta", "Te devolvimos {amount} USDT que enviaste a {name}."),
        "en": ("Transfer returned", "We returned the {amount} USDT you sent to {name}."),
    },
    "mock_location": {
        "es": (
            "Desactiva la ubicación simulada",
            "Detectamos una ubicación simulada y te desconectamos. "
            "Desactívala para recibir viajes.",
        ),
        "en": (
            "Turn off the simulated location",
            "We detected a simulated location and took you offline. Turn it off to receive rides.",
        ),
    },
}
