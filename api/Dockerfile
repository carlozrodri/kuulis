# syntax=docker/dockerfile:1.7
# One image, three process types (PROCESS_TYPE=api|worker|scheduler).

FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000 \
    PROCESS_TYPE=api
RUN apt-get update && apt-get install -y --no-install-recommends curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD test "$PROCESS_TYPE" != "api" || curl -fsS "http://127.0.0.1:${PORT}/health/live" || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
