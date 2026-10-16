#!/usr/bin/env python
"""Django-style management commands.

python manage.py runserver
python manage.py migrate
python manage.py makemigrations "add orders"
python manage.py createsuperuser --email admin@example.com
python manage.py worker | scheduler
python manage.py shell
python manage.py error-codes
"""

import asyncio
import getpass
import os
import subprocess
import sys

import typer

cli = typer.Typer(help="Kuulis management commands", no_args_is_help=True)


def _run(cmd: list[str]) -> None:
    raise typer.Exit(subprocess.call(cmd))  # noqa: S603


@cli.command()
def runserver(host: str = "0.0.0.0", port: int = 8000, reload: bool = True) -> None:  # noqa: S104
    """Development server with autoreload."""
    cmd = ["uvicorn", "kuulis.asgi:app", "--host", host, "--port", str(port)]
    _run([*cmd, "--reload"] if reload else cmd)


@cli.command()
def migrate(revision: str = "head") -> None:
    """Apply database migrations."""
    _run(["alembic", "upgrade", revision])


@cli.command()
def makemigrations(message: str) -> None:
    """Autogenerate a migration from model changes."""
    _run(["alembic", "revision", "--autogenerate", "-m", message])


@cli.command()
def worker(workers: int = 2) -> None:
    """Background job worker."""
    from kuulis.tasks import TASK_MODULES

    _run(["taskiq", "worker", "kuulis.tasks:broker", *TASK_MODULES, "--workers", str(workers)])


@cli.command("error-codes")
def error_codes(check: bool = False) -> None:
    """Write every API error code to the app's i18n folder (doc 20); --check only compares."""
    from kuulis.core.error_codes import EXPORT_PATH, render

    current = EXPORT_PATH.read_text() if EXPORT_PATH.exists() else ""
    if check:
        if current != render():
            typer.echo(f"{EXPORT_PATH} is out of date: run python manage.py error-codes")
            raise typer.Exit(1)
        return
    EXPORT_PATH.write_text(render())
    typer.echo(f"Wrote {EXPORT_PATH}")


@cli.command()
def scheduler() -> None:
    """Periodic job scheduler (run exactly one instance)."""
    from kuulis.tasks import TASK_MODULES

    _run(["taskiq", "scheduler", "kuulis.tasks:scheduler", *TASK_MODULES])


@cli.command()
def createsuperuser(
    email: str = typer.Option(None, envvar="FIRST_SUPERUSER_EMAIL"),
    password: str = typer.Option(None, envvar="FIRST_SUPERUSER_PASSWORD"),
    full_name: str = "Admin",
    no_input: bool = typer.Option(False, "--no-input", help="Skip silently if already exists."),
) -> None:
    """Create an admin user (idempotent with --no-input, used on deploy)."""
    from apps.users import services
    from apps.users.models import Role
    from apps.users.schemas import UserCreate
    from kuulis.core.db import SessionLocal, engine

    if not email:
        if no_input:
            typer.echo("No superuser email configured, skipping.")
            return
        email = typer.prompt("Email")
    if not password:
        if no_input:
            typer.echo("No superuser password configured, skipping.")
            return
        password = getpass.getpass("Password: ")

    async def _create() -> None:
        async with SessionLocal() as session:
            existing = await services.get_by_email(session, email)
            if existing:
                typer.echo(f"User {email} already exists.")
            else:
                await services.create_user(
                    session,
                    UserCreate(email=email, password=password, full_name=full_name),
                    role=Role.ADMIN,
                    is_verified=True,
                )
                await session.commit()
                typer.echo(f"Superuser {email} created.")
        await engine.dispose()

    asyncio.run(_create())


def _loadtest(action) -> None:
    """Runs ``action(session)`` from apps.loadtest.services and prints its JSON result."""
    import json

    import kuulis.models  # noqa: F401  (every table, for clean's foreign key walk)
    from apps.loadtest.services import LoadTestRefusedError
    from kuulis.core.db import SessionLocal, engine

    async def _run() -> None:
        async with SessionLocal() as session:
            try:
                result = await action(session)
            except LoadTestRefusedError as exc:
                typer.echo(f"Refused: {exc}", err=True)
                raise typer.Exit(1) from exc
        typer.echo(json.dumps(result, indent=2, default=str))
        await engine.dispose()

    asyncio.run(_run())


@cli.command("loadtest-seed")
def loadtest_seed(
    password: str = typer.Option(..., envvar="LOADTEST_PASSWORD"),
    passengers: int = 5000,
    drivers: int = 600,
    admins: int = 7,  # 5 for the admin scenario, 2 to send and approve the push campaign
    rides: int = 100_000,
) -> None:
    """Synthetic accounts and ride history for the load tests (doc 18; never in production)."""
    from apps.loadtest import services

    _loadtest(lambda s: services.seed(s, password, passengers, drivers, admins, rides))


@cli.command("loadtest-report")
def loadtest_report(since: str = typer.Option(..., help="ISO time the test started")) -> None:
    """Dispatch times and outcomes of the rides synthetic riders requested since ``since``."""
    from datetime import datetime

    from apps.loadtest import services

    _loadtest(lambda s: services.report(s, datetime.fromisoformat(since)))


@cli.command("loadtest-pgstats")
def loadtest_pgstats(samples: int = 1, every: float = 5.0) -> None:
    """Snapshot of Postgres connections, waits and slowest statements (run during a test)."""
    from apps.loadtest import services

    _loadtest(lambda s: services.pg_stats(s, samples, every))


@cli.command("loadtest-clean")
def loadtest_clean() -> None:
    """Deletes every synthetic account and what it produced."""
    from apps.loadtest import services

    _loadtest(services.clean)


@cli.command()
def shell() -> None:
    """Python shell with settings and models loaded (use `await` with python -m asyncio)."""
    os.execvp(sys.executable, [sys.executable, "-m", "asyncio"])  # noqa: S606


if __name__ == "__main__":
    cli()
