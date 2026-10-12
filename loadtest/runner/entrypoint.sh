#!/bin/sh
set -e
# TARGET_IP: reach BASE_URL's host through this address (e.g. the Nginx Proxy Manager on the LAN)
# while keeping the real hostname for TLS and routing.
if [ -n "$TARGET_IP" ]; then
  host=$(echo "$BASE_URL" | sed -E 's#^[a-z]+://([^/:]+).*#\1#')
  echo "$TARGET_IP $host" >> /etc/hosts
fi
exec uvicorn app:app --app-dir /app/runner --host 0.0.0.0 --port "${PORT:-8080}" --no-access-log
