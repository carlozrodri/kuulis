#!/bin/sh
set -e

case "${PROCESS_TYPE:-api}" in
  api)
    if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
      echo "Running migrations..."
      alembic upgrade head
      python manage.py createsuperuser --no-input || echo "Superuser bootstrap skipped"
    fi
    # A worker recycled by --max-requests drops its WebSockets and in-flight requests (502 at the
    # proxy): at 10k it happened every few minutes per worker under load (doc 18). Requests are
    # logged by RequestContextMiddleware, so gunicorn's access log would only duplicate them.
    exec gunicorn kuulis.asgi:app \
      --worker-class uvicorn_worker.UvicornWorker \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --graceful-timeout 30 \
      --keep-alive 5 \
      --max-requests "${GUNICORN_MAX_REQUESTS:-200000}" \
      --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-20000}" \
      --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"
    ;;
  worker)
    exec taskiq worker kuulis.tasks:broker apps.users.tasks apps.notifications.tasks apps.rides.tasks apps.rates.tasks apps.wallet.tasks apps.monitoring.tasks apps.backups.tasks apps.files.metadata apps.privacy.tasks apps.safety.tasks apps.drivers.tasks apps.support.tasks \
      --workers "${WORKER_CONCURRENCY:-2}" --max-async-tasks "${WORKER_MAX_ASYNC_TASKS:-100}"
    ;;
  scheduler)
    exec taskiq scheduler kuulis.tasks:scheduler apps.users.tasks apps.notifications.tasks apps.rides.tasks apps.rates.tasks apps.wallet.tasks apps.monitoring.tasks apps.backups.tasks apps.files.metadata apps.privacy.tasks apps.safety.tasks apps.drivers.tasks apps.support.tasks
    ;;
  *)
    exec "$@"
    ;;
esac
