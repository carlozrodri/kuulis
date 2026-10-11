"""Backups: encrypted Postgres dumps, a daily ledger export in CSV, a mirror of the uploaded files
and a weekly restore check. Everything goes to the backup bucket under ``<APP_ENV>/``.

Every file is encrypted with ``openssl enc -aes-256-cbc -pbkdf2`` and ``BACKUP_PASSPHRASE``, so a
restore only needs openssl and the PostgreSQL tools (see docs/deployment.md, "Restaurar"):

    openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in X.dump.enc -out X.dump
    pg_restore --no-owner --clean --if-exists -d "$DATABASE_URL" X.dump
"""

import asyncio
import logging
import os
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import orjson

from apps.backups.store import AppFiles, BackupStore
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

STATUS_KEY = f"{settings.APP_ENV}:backups:status"
DUMPS = f"{settings.APP_ENV}/postgres/"
# Every dump goes to recent/; the first of each day also to daily/. The bucket's lifecycle and
# lock rules keep them (docs/deployment.md, "Backups"): the app never deletes a dump.
RECENT = f"{DUMPS}recent/"
DAILY = f"{DUMPS}daily/"
LEDGER = f"{settings.APP_ENV}/ledger/"
FILES = f"{settings.APP_ENV}/files/"
LEDGER_TABLES = ("wallets", "wallet_entries", "wallet_top_ups", "subscription_charges")
RESTORE_DB = f"kuulis_restore_check_{settings.APP_ENV}"
# Row counts compared after a restore (a dump with empty key tables is not a good backup).
RESTORE_TABLES = ("users", "rides", "wallet_entries")


class BackupError(Exception):
    pass


def libpq_url(database: str | None = None) -> str:
    url = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://", 1)
    if database:
        base, _, query = url.partition("?")
        url = base.rsplit("/", 1)[0] + f"/{database}" + (f"?{query}" if query else "")
    return url


async def _run(*args: str, stdout: Path | None = None) -> str:
    """Runs a tool (never through a shell); raises with its stderr on failure."""
    env = {**os.environ, "BACKUP_PASSPHRASE": settings.BACKUP_PASSPHRASE}
    out = stdout.open("wb") if stdout else asyncio.subprocess.PIPE
    try:
        process = await asyncio.create_subprocess_exec(
            *args, stdout=out, stderr=asyncio.subprocess.PIPE, env=env
        )
        output, error = await process.communicate()
    finally:
        if stdout:
            out.close()
    if process.returncode != 0:
        # The first argument names the tool; the URL (with the password) never reaches the logs.
        raise BackupError(f"{args[0]} failed: {error.decode(errors='replace')[-500:]}")
    return output.decode(errors="replace") if output else ""


async def encrypt(source: Path, target: Path) -> None:
    await _run(
        "openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt",
        "-pass", "env:BACKUP_PASSPHRASE", "-in", str(source), "-out", str(target),
    )  # fmt: skip


async def decrypt(source: Path, target: Path) -> None:
    await _run(
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2",
        "-pass", "env:BACKUP_PASSPHRASE", "-in", str(source), "-out", str(target),
    )  # fmt: skip


async def status() -> dict:
    raw = await redis_client.hgetall(STATUS_KEY)
    return {key: orjson.loads(value) for key, value in raw.items()}


async def record(**values: object) -> None:
    await redis_client.hset(STATUS_KEY, mapping={k: orjson.dumps(v) for k, v in values.items()})


def _stamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


async def backup_database(store: BackupStore, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    key = f"{RECENT}{now:%Y/%m/%d}/{_stamp(now)}.dump.enc"
    daily = (await status()).get("last_daily_day") != now.date().isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        plain, sealed = Path(tmp, "db.dump"), Path(tmp, "db.dump.enc")
        started = time.monotonic()
        await _run(
            "pg_dump", "--format=custom", "--no-owner", "--no-acl", libpq_url(), stdout=plain
        )
        await encrypt(plain, sealed)
        size = (await asyncio.to_thread(sealed.stat)).st_size
        await asyncio.to_thread(store.put, key, sealed)
        if daily:
            await asyncio.to_thread(store.put, f"{DAILY}{now:%Y/%m}/{_stamp(now)}.dump.enc", sealed)
    values: dict[str, object] = {
        "last_backup_at": now.isoformat(),
        "last_backup_key": key,
        "last_backup_bytes": size,
        "last_backup_seconds": round(time.monotonic() - started, 1),
    }
    if daily:
        values["last_daily_day"] = now.date().isoformat()
    await record(**values)
    logger.info("Database backup %s (%s bytes)", key, size)
    return key


async def export_ledger(store: BackupStore, now: datetime | None = None) -> str:
    """Money tables as CSV, readable without PostgreSQL (accounting copy)."""
    now = now or datetime.now(UTC)
    key = f"{LEDGER}{now:%Y/%m}/{now:%Y-%m-%d}.tar.gz.enc"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        archive, sealed = folder / "ledger.tar.gz", folder / "ledger.tar.gz.enc"
        with tarfile.open(archive, "w:gz") as tar:
            for table in LEDGER_TABLES:
                csv = folder / f"{table}.csv"
                await _run(
                    "psql", libpq_url(), "--no-psqlrc", "-v", "ON_ERROR_STOP=1", "-c",
                    f"\\copy (SELECT * FROM {table} ORDER BY 1) TO STDOUT WITH CSV HEADER",  # noqa: S608 (constant names)
                    stdout=csv,
                )  # fmt: skip
                tar.add(csv, arcname=f"{table}.csv")
        await encrypt(archive, sealed)
        await asyncio.to_thread(store.put, key, sealed)
    await record(last_ledger_at=now.isoformat(), last_ledger_key=key)
    return key


async def mirror_files(store: BackupStore, files: AppFiles) -> dict[str, int]:
    """Copies new uploads (encrypted) and removes the ones deleted from the app (account erasure
    must reach the copies too). Keys are unique and never rewritten, so presence is enough."""
    source_prefix = f"{settings.STORAGE_PREFIX}/"
    source_objects = await asyncio.to_thread(files.list_objects, source_prefix)
    source = {o.key[len(source_prefix) :] for o in source_objects}
    backup_objects = await asyncio.to_thread(store.list_objects, FILES)
    mirrored = {o.key[len(FILES) :].removesuffix(".enc") for o in backup_objects}
    copied = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name in sorted(source - mirrored):
            plain, sealed = Path(tmp, "file"), Path(tmp, "file.enc")
            await asyncio.to_thread(files.get, source_prefix + name, plain)
            await encrypt(plain, sealed)
            await asyncio.to_thread(store.put, f"{FILES}{name}.enc", sealed)
            copied += 1
    removed = [f"{FILES}{name}.enc" for name in mirrored - source]
    if removed:
        await asyncio.to_thread(store.delete, removed)
    result = {"copied": copied, "removed": len(removed), "total": len(source)}
    await record(last_files_mirror_at=datetime.now(UTC).isoformat(), last_files_mirror=result)
    return result


async def restore_check(store: BackupStore) -> dict:
    """Restores the newest dump into a scratch database, counts key rows and drops it."""
    objects = await asyncio.to_thread(store.list_objects, DUMPS)
    dumps = sorted(
        (o for o in objects if o.key.endswith(".dump.enc")), key=lambda o: o.key.rsplit("/", 1)[-1]
    )
    if not dumps:
        raise BackupError("No database backup to restore")
    latest = dumps[-1]
    started = time.monotonic()
    admin = libpq_url()
    with tempfile.TemporaryDirectory() as tmp:
        sealed, plain = Path(tmp, "db.dump.enc"), Path(tmp, "db.dump")
        await asyncio.to_thread(store.get, latest.key, sealed)
        await decrypt(sealed, plain)
        await _run("psql", admin, "--no-psqlrc", "-c", f'DROP DATABASE IF EXISTS "{RESTORE_DB}"')
        await _run("psql", admin, "--no-psqlrc", "-c", f'CREATE DATABASE "{RESTORE_DB}"')
        try:
            await _run(
                "pg_restore", "--no-owner", "--no-acl", "-d", libpq_url(RESTORE_DB), str(plain)
            )
            query = (
                " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in RESTORE_TABLES)  # noqa: S608
                + " UNION ALL SELECT 'alembic:' || version_num, 0 FROM alembic_version"
            )
            rows = await _run(
                "psql", libpq_url(RESTORE_DB), "--no-psqlrc", "-At", "-F", "=", "-c", query
            )
        finally:
            await _run(
                "psql", admin, "--no-psqlrc", "-c", f'DROP DATABASE IF EXISTS "{RESTORE_DB}"'
            )
    counts = dict(line.split("=", 1) for line in rows.strip().splitlines())
    result = {
        "key": latest.key,
        "seconds": round(time.monotonic() - started, 1),
        "alembic": next((k.split(":", 1)[1] for k in counts if k.startswith("alembic:")), None),
        "rows": {t: int(counts[t]) for t in RESTORE_TABLES},
    }
    await record(
        last_restore_check_at=datetime.now(UTC).isoformat(),
        last_restore_ok=True,
        last_restore=result,
    )
    logger.info("Restore check passed: %s", result)
    return result
