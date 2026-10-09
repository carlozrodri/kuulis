# Kuulis API

FastAPI organized like a Django project:

```
api/
├── manage.py              # Django-style commands (runserver, migrate, makemigrations, createsuperuser, worker…)
├── kuulis/                # "project" package
│   ├── settings/          # base.py + local / test / qa / production (APP_ENV picks one)
│   ├── asgi.py            # app factory, middleware, lifespan
│   ├── urls.py            # mounts every app router under /api/v1
│   ├── models.py          # registry of all models (INSTALLED_APPS equivalent)
│   ├── tasks.py           # Taskiq broker + scheduler (celery.py equivalent)
│   └── core/              # db, redis, security, cache, storage, email, rate limit, errors, logging
├── apps/                  # one folder per domain app
│   └── <app>/  models.py  schemas.py  services.py  router.py  dependencies.py  tasks.py  tests/
├── migrations/            # Alembic
└── docker/entrypoint.sh   # PROCESS_TYPE=api|worker|scheduler
```

## Local development

```bash
docker compose up -d            # postgres + redis (or use your own)
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver        # http://localhost:8000/api/v1/docs
uv run python manage.py worker           # background jobs, in another terminal
```

## Tests and lint

```bash
createdb kuulis_test             # once
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Apps

| App | What it does |
| --- | --- |
| `auth` | Email/password login, rotating refresh tokens, email verification, password reset, Google and Apple sign-in (`/auth/social/google`, `/auth/social/apple`). |
| `users` | Profile, roles (`user`, `staff`, `admin`), admin user management. |
| `config` | Admin-editable settings (driver min age, min vehicle year, required documents...) stored as JSONB and cached in Redis. Other apps call `apps.config.services.get_app_config(session)`. |
| `drivers` | Driver onboarding: profile, vehicle, documents in private S3, review workflow (`draft → pending_review → approved/rejected`, `approved ↔ suspended`) and admin endpoints under `/admin/drivers`. |
| `notifications` | Push (Expo) + in-app inbox. |
| `files` | Presigned S3 uploads/downloads. |
| `realtime` | WebSocket fan-out through Redis pub/sub. |

The HTTP contract shared with the apps lives in `docs/api/`.

## Social login

Set the accepted OAuth audiences as comma separated lists. An empty list disables that provider
(`social_provider_disabled`).

```bash
GOOGLE_CLIENT_IDS=<web client id>,<ios client id>,<android client id>
APPLE_CLIENT_IDS=<ios bundle id>
```

ID tokens are verified against the providers' public keys (JWKS, cached in Redis for 6 hours and
refetched when an unknown key id shows up).

## Adding an app

1. `mkdir apps/<name>` with `models.py`, `schemas.py`, `services.py`, `router.py`, `tests/`.
2. Import its models in `kuulis/models.py` and mount its router in `kuulis/urls.py`.
3. If it has jobs, add `apps.<name>.tasks` to `TASK_MODULES` in `kuulis/tasks.py` and `docker/entrypoint.sh`.
4. `uv run python manage.py makemigrations "add <name>"` and review the generated file.

Conventions: routers are thin, business logic lives in `services.py`, errors are raised as
`AppError` subclasses with a stable `code` the clients translate.
