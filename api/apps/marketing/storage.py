"""The marketing bucket (docs/marketing/09 §1.1): same S3 endpoint as the rest of the API, its own
bucket and key so content never mixes with drivers' documents or their deletion rules.

Keys: ``marketing/<STORAGE_PREFIX>/<yyyy>/<mm>/<code>/<role folder>/<8 hex>-<name>``. The random
part keeps every take (nothing is overwritten); the code finds the files from the registry."""

import logging
import re
import secrets
from datetime import datetime
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from kuulis.core.exceptions import ServiceUnavailableError
from kuulis.core.storage import StorageCheckUnavailable
from kuulis.settings import settings

logger = logging.getLogger(__name__)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
ROLE_FOLDERS = {"original": "original", "final": "final", "portada": "portada", "fuente": "fuentes"}


@lru_cache
def get_client() -> BaseClient:
    if not settings.marketing_storage_enabled:
        raise ServiceUnavailableError(
            "The marketing bucket is not configured", code="marketing_storage_disabled"
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT or None,
        aws_access_key_id=settings.MARKETING_S3_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=(
            settings.MARKETING_S3_SECRET_ACCESS_KEY or settings.AWS_SECRET_ACCESS_KEY
        ),
        region_name=settings.AWS_S3_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=3,
            read_timeout=5,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def content_prefix(code: str, created_at: datetime) -> str:
    return f"marketing/{settings.STORAGE_PREFIX}/{created_at:%Y/%m}/{code}/"


def build_key(code: str, created_at: datetime, role: str, filename: str) -> str:
    safe = _SAFE_NAME.sub("-", filename).strip("-")[:120] or "archivo"
    return f"{content_prefix(code, created_at)}{ROLE_FOLDERS[role]}/{secrets.token_hex(4)}-{safe}"


def presigned_upload(key: str, content_type: str) -> str:
    return get_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.MARKETING_S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )


def presigned_download(key: str, filename: str | None = None) -> str:
    params: dict[str, Any] = {"Bucket": settings.MARKETING_S3_BUCKET, "Key": key}
    if filename:
        # The phone saves it with a readable name (K-2026-11-04-A-tiktok.mp4), not the S3 key.
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return get_client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=settings.MARKETING_DOWNLOAD_URL_SECONDS
    )


def download_url_or_none(key: str | None, filename: str | None = None) -> str | None:
    if not key:
        return None
    try:
        return presigned_download(key, filename)
    except ServiceUnavailableError:
        return None
    except Exception:
        logger.warning("Could not sign marketing download URL", exc_info=True)
        return None


def head_object(key: str) -> dict[str, Any] | None:
    """Object metadata, None when missing; ``StorageCheckUnavailable`` when S3 can't tell."""
    try:
        return get_client().head_object(Bucket=settings.MARKETING_S3_BUCKET, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        logger.warning("Marketing HeadObject failed with %s for %s", code, key)
        raise StorageCheckUnavailable(str(code)) from exc
    except BotoCoreError as exc:
        raise StorageCheckUnavailable(type(exc).__name__) from exc
