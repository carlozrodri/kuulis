"""Structured logging. JSON in deployed environments, readable text locally."""

import logging
import sys
from datetime import UTC, datetime

import orjson

from kuulis.core.request_context import request_id_ctx
from kuulis.settings import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "env": settings.APP_ENV,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return orjson.dumps(payload).decode()


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_JSON:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL)
    for noisy in ("uvicorn.access", "httpx", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
