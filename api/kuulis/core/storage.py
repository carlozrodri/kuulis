"""S3 compatible object storage (presigned uploads/downloads).

Files are stored under ``<STORAGE_PREFIX>/<folder>/<uuid>-<name>`` so QA and production can share
one bucket without colliding.
"""

import re
import uuid
from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from kuulis.core.exceptions import ServiceUnavailableError
from kuulis.settings import settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


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


def build_key(folder: str, filename: str) -> str:
    safe = _SAFE_NAME.sub("-", filename).strip("-")[:120] or "file"
    return f"{settings.STORAGE_PREFIX}/{folder.strip('/')}/{uuid.uuid4().hex}-{safe}"


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
