#!/usr/bin/env python
"""Django-style management commands.

python manage.py runserver
python manage.py migrate
python manage.py makemigrations "add orders"
python manage.py createsuperuser --email admin@example.com
python manage.py worker | scheduler
python manage.py shell
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


@cli.command()
def shell() -> None:
    """Python shell with settings and models loaded (use `await` with python -m asyncio)."""
    os.execvp(sys.executable, [sys.executable, "-m", "asyncio"])  # noqa: S606


if __name__ == "__main__":
    cli()
