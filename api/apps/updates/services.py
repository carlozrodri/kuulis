"""JavaScript updates (OTA) served with the Expo Updates protocol v1 (doc 09).

The compiler (``mobile/builder``) exports every change that does not touch native code and uploads
its files to ``updates/<APP_ENV>/assets/<sha256>`` (each file once) next to a candidate JSON in
``updates/<APP_ENV>/candidates/``. Publishing a candidate from the admin creates an ``AppUpdate``;
the apps ask ``GET /updates/manifest`` on every launch and receive the newest update of their
channel and runtime version, signed with ``UPDATES_SIGNING_KEY`` (the app refuses anything not
signed by the certificate it was built with). The asset links are presigned S3 URLs.

A rollout below 100 % reaches a stable share of the devices: each device's ``EAS-Client-ID``
(a random id the app keeps) is hashed with the update id. Devices outside the share get the
previous update. Reverting withdraws the update and publishes a newer copy of the previous one
(apps keep the newest update they downloaded, so serving an older one would not be enough); with
nothing before it, a ``rollBackToEmbedded`` directive sends them back to the code inside the APK.
"""

import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.releases.services import PLATFORMS
from apps.updates.models import AppUpdate
from apps.updates.schemas import (
    CandidateRead,
    UpdateCandidate,
    UpdatePatch,
    UpdatePublish,
    UpdateUsage,
)
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from kuulis.settings import settings

logger = logging.getLogger(__name__)

ASSET_LINK_SECONDS = 6 * 3600
# Signed manifests are reused for a few minutes (presigning ~100 links and an RSA signature per
# launch adds up with thousands of apps); well below ASSET_LINK_SECONDS.
MANIFEST_CACHE_SECONDS = 300
USAGE_DAYS = 7


class CandidateNotFoundError(NotFoundError):
    code = "update_candidate_not_found"
    message = "That update is not in storage"


class UpdateExistsError(ConflictError):
    code = "update_exists"
    message = "That update is already published in this channel"


class NothingToRevertError(ConflictError):
    code = "update_not_current"
    message = "Only an update that is still offered can be reverted"


class UpdateRequestError(AppError):
    status_code = 400
    code = "invalid_update_request"
    message = "The update request is missing a valid platform or runtime version"


class SigningUnavailableError(ServiceUnavailableError):
    code = "updates_signing_disabled"
    message = "Updates cannot be signed: the signing key is not configured"


def prefix() -> str:
    return f"updates/{settings.APP_ENV}/"


def candidates_prefix() -> str:
    return f"{prefix()}candidates/"


def assets_prefix() -> str:
    return f"{prefix()}assets/"


# --- Signing -------------------------------------------------------------------------------------


@lru_cache
def _private_key(pem: str) -> rsa.RSAPrivateKey:
    key = serialization.load_pem_private_key(pem.replace("\\n", "\n").encode(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("UPDATES_SIGNING_KEY must be an RSA key")
    return key


def signing_enabled() -> bool:
    return bool(settings.UPDATES_SIGNING_KEY)


def signature_header(body: bytes) -> str:
    """``expo-signature`` (Expo SFV dictionary): RSA PKCS#1 v1.5 with SHA-256, base64."""
    if not signing_enabled():
        raise SigningUnavailableError()
    try:
        key = _private_key(settings.UPDATES_SIGNING_KEY)
    except ValueError as exc:
        logger.error("UPDATES_SIGNING_KEY is not a valid RSA private key")
        raise SigningUnavailableError() from exc
    sig = base64.b64encode(key.sign(body, padding.PKCS1v15(), hashes.SHA256())).decode()
    return f'sig="{sig}", keyid="{settings.UPDATES_SIGNING_KEY_ID}"'


# --- Which update a device gets ----------------------------------------------------------------


def in_rollout(update: AppUpdate, client_id: str | None) -> bool:
    if update.rollout_percent >= 100:
        return True
    if update.rollout_percent <= 0 or not client_id:
        return False
    digest = hashlib.sha256(f"{update.id}:{client_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100 < update.rollout_percent


async def offered(
    session: AsyncSession, platform: str, channel: str, runtime_version: str
) -> list[AppUpdate]:
    """Updates still offered for this binary, newest first."""
    rows = await session.scalars(
        select(AppUpdate)
        .where(
            AppUpdate.platform == platform,
            AppUpdate.channel == channel,
            AppUpdate.runtime_version == runtime_version,
            AppUpdate.withdrawn_at.is_(None),
        )
        .order_by(AppUpdate.created_at.desc())
        .limit(20)
    )
    return list(rows)


async def select_update(
    session: AsyncSession,
    platform: str,
    channel: str,
    runtime_version: str,
    client_id: str | None,
) -> AppUpdate | None:
    for update in await offered(session, platform, channel, runtime_version):
        if in_rollout(update, client_id):
            return update
    return None


# --- Response bodies ---------------------------------------------------------------------------


def _asset(item: dict, expires_in: int) -> dict:
    asset = {
        "hash": item["hash"],
        "key": item["key"],
        "contentType": item["contentType"],
        "url": storage.presigned_download(item["s3_key"], expires_in),
    }
    if item.get("fileExtension"):
        asset["fileExtension"] = item["fileExtension"]
    return asset


def manifest(update: AppUpdate) -> dict:
    return {
        "id": str(update.id),
        "createdAt": update.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "runtimeVersion": update.runtime_version,
        "launchAsset": _asset(update.launch_asset or {}, ASSET_LINK_SECONDS),
        "assets": [_asset(a, ASSET_LINK_SECONDS) for a in update.assets],
        "metadata": {},
        "extra": update.extra or {},
    }


def directive(update: AppUpdate) -> dict:
    """Back to the code inside the APK (``commitTime`` makes it newer than what the app has)."""
    created = update.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {"type": "rollBackToEmbedded", "parameters": {"commitTime": created}}


_cache: dict[tuple[uuid.UUID, bool], tuple[float, bytes, str | None]] = {}


def response_part(update: AppUpdate, signed: bool) -> tuple[str, bytes, str | None]:
    """(part name, JSON body, expo-signature) for the update; cached for a few minutes."""
    name = "directive" if update.kind == "rollback" else "manifest"
    cached = _cache.get((update.id, signed))
    if cached and cached[0] > time.monotonic():
        return name, cached[1], cached[2]
    data = directive(update) if update.kind == "rollback" else manifest(update)
    body = json.dumps(data, separators=(",", ":")).encode()
    signature = signature_header(body) if signed else None
    if len(_cache) > 200:
        _cache.clear()
    _cache[(update.id, signed)] = (time.monotonic() + MANIFEST_CACHE_SECONDS, body, signature)
    return name, body, signature


def multipart(parts: list[tuple[str, bytes, str | None]]) -> tuple[bytes, str]:
    """``multipart/mixed`` body and its boundary."""
    boundary = f"kuulis-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, body, signature in parts:
        headers = [
            f'content-disposition: form-data; name="{name}"',
            "content-type: application/json; charset=utf-8",
        ]
        if signature:
            headers.append(f"expo-signature: {signature}")
        header_block = "".join(f"{h}\r\n" for h in headers)
        chunks.append(f"--{boundary}\r\n{header_block}\r\n".encode())
        chunks.append(body + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


# --- Candidates uploaded by the compiler --------------------------------------------------------


def _read_candidate(key: str) -> UpdateCandidate:
    data = json.loads(storage.get_object_bytes(key, max_bytes=2_000_000))
    return UpdateCandidate.model_validate({**data, "key": key})


def _list_candidates(limit: int) -> list[UpdateCandidate]:
    found: list[UpdateCandidate] = []
    for obj in storage.list_objects(candidates_prefix(), limit=200):
        if not obj["Key"].endswith(".json"):
            continue
        try:
            found.append(_read_candidate(obj["Key"]))
        except Exception:
            logger.warning("Unreadable update candidate %s", obj["Key"], exc_info=True)
        if len(found) >= limit:
            break
    return found


async def candidates(session: AsyncSession, limit: int = 20) -> list[CandidateRead]:
    try:
        found = await asyncio.to_thread(_list_candidates, limit)
    except ServiceUnavailableError:
        raise
    except Exception as exc:
        logger.warning("Could not list update candidates", exc_info=True)
        raise ServiceUnavailableError(
            "Storage is not answering", code="storage_unavailable"
        ) from exc
    published = await session.execute(
        select(AppUpdate.source_key, AppUpdate.channel).where(
            AppUpdate.withdrawn_at.is_(None), AppUpdate.reverted_from_id.is_(None)
        )
    )
    channels: dict[str, set[str]] = {}
    for key, channel in published:
        channels.setdefault(key, set()).add(channel)
    return [
        CandidateRead(
            key=c.key,
            platform=c.platform,
            runtime_version=c.runtime_version,
            commit=c.commit,
            message=c.message,
            built_at=c.built_at,
            bundle_size=c.bundle_size,
            asset_count=len(c.assets) + 1,
            published_channels=sorted(channels.get(c.key, set())),
        )
        for c in found
    ]


def _valid_candidate_key(key: str) -> bool:
    rest = key[len(candidates_prefix()) :]
    return (
        key.startswith(candidates_prefix())
        and key.endswith(".json")
        and "/" not in rest
        and ".." not in key
    )


def _valid_asset_key(key: str) -> bool:
    rest = key[len(assets_prefix()) :]
    return key.startswith(assets_prefix()) and bool(rest) and "/" not in rest and ".." not in key


async def publish(session: AsyncSession, admin: User, data: UpdatePublish) -> AppUpdate:
    if not _valid_candidate_key(data.candidate_key):
        raise CandidateNotFoundError()
    try:
        candidate = await asyncio.to_thread(_read_candidate, data.candidate_key)
    except Exception as exc:
        raise CandidateNotFoundError() from exc
    every = [candidate.launch_asset, *candidate.assets]
    if not all(_valid_asset_key(a.s3_key) for a in every):
        raise CandidateNotFoundError()
    exists = await session.scalar(
        select(AppUpdate.id).where(
            AppUpdate.source_key == data.candidate_key,
            AppUpdate.channel == data.channel,
            AppUpdate.withdrawn_at.is_(None),
            AppUpdate.reverted_from_id.is_(None),
        )
    )
    if exists is not None:
        raise UpdateExistsError()
    update = AppUpdate(
        platform=candidate.platform,
        channel=data.channel,
        runtime_version=candidate.runtime_version,
        kind="update",
        source_key=data.candidate_key,
        commit=candidate.commit,
        message=data.message or candidate.message,
        launch_asset=candidate.launch_asset.model_dump(),
        assets=[a.model_dump() for a in candidate.assets],
        extra=candidate.extra,
        rollout_percent=data.rollout_percent,
        published_by_id=admin.id,
        created_at=datetime.now(UTC),
    )
    session.add(update)
    await session.flush()
    return update


async def update(session: AsyncSession, update_id: uuid.UUID, data: UpdatePatch) -> AppUpdate:
    row = await session.get(AppUpdate, update_id)
    if row is None:
        raise NotFoundError()
    if data.rollout_percent is not None:
        row.rollout_percent = data.rollout_percent
    if "message" in data.model_fields_set:
        row.message = data.message
    await session.flush()
    return row


async def revert(session: AsyncSession, admin: User, update_id: uuid.UUID) -> AppUpdate:
    """Withdraws the update and publishes what the apps should run instead (see the module doc)."""
    row = await session.get(AppUpdate, update_id)
    if row is None:
        raise NotFoundError()
    if row.withdrawn_at is not None:
        raise NothingToRevertError()
    now = datetime.now(UTC)
    row.withdrawn_at = now
    previous = next(
        (
            u
            for u in await offered(session, row.platform, row.channel, row.runtime_version)
            if u.id != row.id and u.created_at < row.created_at and u.rollout_percent >= 100
        ),
        None,
    )
    replacement = AppUpdate(
        platform=row.platform,
        channel=row.channel,
        runtime_version=row.runtime_version,
        rollout_percent=100,
        reverted_from_id=row.id,
        published_by_id=admin.id,
        # A moment after the withdrawn one, so it is newer than anything an app downloaded.
        created_at=max(now, row.created_at + timedelta(seconds=1)),
    )
    if previous is not None and previous.kind == "update":
        replacement.kind = "update"
        replacement.source_key = previous.source_key
        replacement.commit = previous.commit
        replacement.message = previous.message
        replacement.launch_asset = previous.launch_asset
        replacement.assets = previous.assets
        replacement.extra = previous.extra
        previous.withdrawn_at = now  # the copy replaces it
    else:
        replacement.kind = "rollback"
        replacement.assets = []
        replacement.extra = {}
        if previous is not None:
            previous.withdrawn_at = now
    session.add(replacement)
    await session.flush()
    return replacement


async def updates(
    session: AsyncSession, channel: str | None = None
) -> list[tuple[AppUpdate, str | None]]:
    query = (
        select(AppUpdate, User.email)
        .outerjoin(User, User.id == AppUpdate.published_by_id)
        .order_by(AppUpdate.created_at.desc())
        .limit(100)
    )
    if channel:
        query = query.where(AppUpdate.channel == channel)
    return [(u, email) for u, email in await session.execute(query)]


# --- Which updates are running ------------------------------------------------------------------


def _usage_key(day: str, update_id: str) -> str:
    return f"{settings.APP_ENV}:otaver:{day}:{update_id}"


def _ids_key(day: str) -> str:
    return f"{settings.APP_ENV}:otaver:{day}:ids"


def _clean_update_id(raw: str | None) -> str | None:
    """A UUID the app reports, or ``embedded`` for the code inside the APK."""
    if raw == "embedded":
        return raw
    try:
        return str(uuid.UUID(raw or ""))
    except ValueError:
        return None


async def record_usage(
    redis: Redis, platform: str | None, raw_update_id: str | None, user_id: uuid.UUID
) -> None:
    update_id = _clean_update_id(raw_update_id)
    if platform not in PLATFORMS or update_id is None:
        return
    day = datetime.now(UTC).date().isoformat()
    ttl = (USAGE_DAYS + 1) * 86400
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.pfadd(_usage_key(day, update_id), user_id.hex)
            pipe.expire(_usage_key(day, update_id), ttl)
            pipe.sadd(_ids_key(day), update_id)
            pipe.expire(_ids_key(day), ttl)
            await pipe.execute()
    except Exception:
        logger.warning("Could not record OTA usage", exc_info=True)


async def usage(redis: Redis) -> list[UpdateUsage]:
    """Distinct users per running update over the last 7 days."""
    today = datetime.now(UTC).date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(USAGE_DAYS)]
    seen: set[str] = set()
    for day in days:
        seen |= {
            m.decode() if isinstance(m, bytes) else m for m in await redis.smembers(_ids_key(day))
        }
    result = [
        UpdateUsage(
            update_id=update_id,
            users=await redis.pfcount(*[_usage_key(day, update_id) for day in days]),
        )
        for update_id in seen
    ]
    return sorted(result, key=lambda u: -u.users)
