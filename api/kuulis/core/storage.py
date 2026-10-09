"""S3 compatible object storage (presigned uploads/downloads).

Files are stored under ``<STORAGE_PREFIX>/<folder>/<uuid>-<name>`` so QA and production can share
one bucket without colliding.
"""

import logging
import re
import uuid
from functools import lru_cache
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from kuulis.core.exceptions import ServiceUnavailableError
from kuulis.settings import settings

logger = logging.getLogger(__name__)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class StorageCheckUnavailable(Exception):
    """The API could not read object metadata (e.g. the S3 endpoint refuses server-side reads)."""


@lru_cache
def get_s3_client() -> BaseClient:
    if not settings.storage_enabled:
        raise ServiceUnavailableError("Storage is not configured", code="storage_disabled")
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def folder_prefix(folder: str) -> str:
    """Key prefix of a folder, with trailing slash (``<STORAGE_PREFIX>/<folder>/``)."""
    return f"{settings.STORAGE_PREFIX}/{folder.strip('/')}/"


def build_key(folder: str, filename: str) -> str:
    safe = _SAFE_NAME.sub("-", filename).strip("-")[:120] or "file"
    return f"{folder_prefix(folder)}{uuid.uuid4().hex}-{safe}"


def key_in_folder(key: str, folder: str) -> bool:
    """True when ``key`` was built by ``build_key(folder, ...)`` (no traversal, no subfolders)."""
    prefix = folder_prefix(folder)
    rest = key[len(prefix) :]
    return key.startswith(prefix) and bool(rest) and "/" not in rest and ".." not in key


def head_object(key: str) -> dict[str, Any] | None:
    """Object metadata (``ContentType``, ``ContentLength``...) or None if it does not exist.

    Raises ``StorageCheckUnavailable`` when the storage answers anything other than found/not
    found, so callers can decide whether to trust the presigned upload instead.
    """
    try:
        return get_s3_client().head_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        logger.warning("S3 HeadObject failed with %s for %s", code, key)
        raise StorageCheckUnavailable(str(code)) from exc
    except BotoCoreError as exc:
        logger.warning("S3 HeadObject unreachable for %s: %s", key, exc)
        raise StorageCheckUnavailable(type(exc).__name__) from exc


def presigned_upload(key: str, content_type: str) -> str:
    return get_s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.AWS_S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )


def presigned_download(key: str) -> str:
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_S3_BUCKET, "Key": key},
        ExpiresIn=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )
