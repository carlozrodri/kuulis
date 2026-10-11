import shutil
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from apps.backups import services, tasks
from apps.backups.store import StoredObject
from apps.monitoring import checks
from kuulis.core.db import engine
from kuulis.settings import settings


class FolderStore:
    """Backup bucket on the local disk."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, path: Path) -> None:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, target)

    def get(self, key: str, path: Path) -> None:
        shutil.copy(self.root / key, path)

    def list_objects(self, prefix: str) -> list[StoredObject]:
        return [
            StoredObject(
                str(p.relative_to(self.root)),
                p.stat().st_size,
                datetime.fromtimestamp(p.stat().st_mtime, UTC),
            )
            for p in sorted(self.root.rglob("*"))
            if p.is_file() and str(p.relative_to(self.root)).startswith(prefix)
        ]

    def delete(self, keys: list[str]) -> None:
        for key in keys:
            (self.root / key).unlink()


@pytest.fixture
def store(tmp_path) -> FolderStore:
    return FolderStore(tmp_path / "bucket")


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    for name, value in {
        "BACKUP_ENABLED": True,
        "BACKUP_S3_BUCKET": "backups",
        "BACKUP_S3_ACCESS_KEY_ID": "id",
        "BACKUP_S3_SECRET_ACCESS_KEY": "secret",
        "BACKUP_PASSPHRASE": "correct horse battery staple",
    }.items():
        monkeypatch.setattr(settings, name, value)


async def _decrypt(store: FolderStore, key: str, tmp_path: Path) -> Path:
    plain = tmp_path / "plain"
    await services.decrypt(store.root / key, plain)
    return plain


async def test_dump_is_encrypted_and_restores(store, tmp_path, user_headers):
    async with engine.begin() as conn:  # migrated databases have it; the test schema does not
        await conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num text)"))
        await conn.execute(text("INSERT INTO alembic_version VALUES ('abc123')"))
    try:
        key = await services.backup_database(store)
        assert key.startswith("test/postgres/recent/") and key.endswith(".dump.enc")
        assert b"PGDMP" not in (store.root / key).read_bytes()[:16]  # not a plain dump
        assert (await _decrypt(store, key, tmp_path)).read_bytes()[:5] == b"PGDMP"

        result = await services.restore_check(store)
        assert result["rows"]["users"] == 1 and result["alembic"] == "abc123"
        state = await services.status()
        assert state["last_backup_key"] == key and state["last_restore_ok"] is True
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


async def test_ledger_export_has_the_money_tables(store, tmp_path):
    key = await services.export_ledger(store)
    with tarfile.open(await _decrypt(store, key, tmp_path)) as tar:
        assert sorted(tar.getnames()) == sorted(f"{t}.csv" for t in services.LEDGER_TABLES)


async def test_first_dump_of_the_day_is_also_kept_as_daily(store):
    day = datetime(2026, 10, 20, 0, 5, tzinfo=UTC)
    for minutes in (0, 15, 24 * 60):
        await services.backup_database(store, day + timedelta(minutes=minutes))
    recent = store.list_objects(services.RECENT)
    daily = [o.key for o in store.list_objects(services.DAILY)]
    assert len(recent) == 3
    assert daily == [
        "test/postgres/daily/2026/10/20261020T000500Z.dump.enc",
        "test/postgres/daily/2026/10/20261021T000500Z.dump.enc",
    ]


async def test_file_mirror_copies_new_and_drops_erased(store, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PREFIX", "qa")
    source = FolderStore(tmp_path / "app")
    for name in ("documents/a.jpg", "documents/b.jpg"):
        path = tmp_path / "upload"
        path.write_bytes(name.encode())
        source.put(f"qa/{name}", path)
    store.put("test/files/documents/gone.jpg.enc", tmp_path / "upload")

    result = await services.mirror_files(store, source)
    assert result == {"copied": 2, "removed": 1, "total": 2}
    keys = [o.key for o in store.list_objects("test/files/")]
    assert keys == ["test/files/documents/a.jpg.enc", "test/files/documents/b.jpg.enc"]
    plain = await _decrypt(store, keys[0], tmp_path)
    assert plain.read_bytes() == b"documents/a.jpg"
    assert (await services.mirror_files(store, source))["copied"] == 0


async def test_scheduler_backs_up_once_per_interval(store, monkeypatch):
    monkeypatch.setattr(tasks, "backup_store", lambda: store)
    monkeypatch.setattr(settings, "BACKUP_MIRROR_FILES", False)
    first = await tasks.run_due()
    assert "database" in first
    assert "database" not in await tasks.run_due()  # the next one waits BACKUP_EVERY_MINUTES


async def test_failures_and_stale_backups_alert(store, monkeypatch):
    from kuulis.core.db import SessionLocal

    monkeypatch.setattr(checks, "disk_used_percent", lambda: 40.0)
    async with SessionLocal() as session:
        health = await checks.collect(session)
    assert "backup:stale" in [p.key for p in checks.problems(health)]

    await services.record(last_files_error="AccessDenied")
    await services.backup_database(store)
    async with SessionLocal() as session:
        health = await checks.collect(session)
    keys = [p.key for p in checks.problems(health)]
    assert "backup:stale" not in keys and "backup:files" in keys
    assert health.backups.last_backup_bytes > 0
