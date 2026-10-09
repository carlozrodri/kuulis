#!/bin/sh
set -e

case "${PROCESS_TYPE:-api}" in
  api)
    if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
      echo "Running migrations..."
      alembic upgrade head
      python manage.py createsuperuser --no-input || echo "Superuser bootstrap skipped"
    fi
    exec gunicorn kuulis.asgi:app \
      --worker-class uvicorn_worker.UvicornWorker \
      --bind "0.0.0.0:${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --graceful-timeout 30 \
      --keep-alive 5 \
      --max-requests 10000 \
      --max-requests-jitter 1000 \
      --forwarded-allow-ips "*" \
      --access-logfile -
    ;;
  worker)
    exec taskiq worker kuulis.tasks:broker apps.users.tasks apps.notifications.tasks apps.rides.tasks \
      --workers "${WORKER_CONCURRENCY:-2}" --max-async-tasks "${WORKER_MAX_ASYNC_TASKS:-100}"
    ;;
  scheduler)
    exec taskiq scheduler kuulis.tasks:scheduler apps.users.tasks apps.notifications.tasks apps.rides.tasks
    ;;
  *)
    exec "$@"
    ;;
esac
