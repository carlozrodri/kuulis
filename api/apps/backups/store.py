"""The backup bucket (S3 compatible, Cloudflare R2 by default). Separate from the app's file
storage: different provider, credentials and site, so losing the homelab does not lose the
backups."""

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from kuulis.settings import settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    modified: datetime


class BackupStore(Protocol):
    def put(self, key: str, path: Path) -> None: ...
    def get(self, key: str, path: Path) -> None: ...
    def list_objects(self, prefix: str) -> list[StoredObject]: ...
    def delete(self, keys: list[str]) -> None: ...


def _list(client: BaseClient, bucket: str, prefix: str) -> list[StoredObject]:
    objects = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            objects.append(StoredObject(item["Key"], item["Size"], item["LastModified"]))
    return objects


class S3BackupStore:
    def __init__(self) -> None:
        self.bucket = settings.BACKUP_S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.BACKUP_S3_ENDPOINT or None,
            aws_access_key_id=settings.BACKUP_S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.BACKUP_S3_SECRET_ACCESS_KEY,
            region_name=settings.BACKUP_S3_REGION,
            config=Config(
                signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}
            ),
        )

    def put(self, key: str, path: Path) -> None:
        self.client.upload_file(str(path), self.bucket, key)

    def get(self, key: str, path: Path) -> None:
        self.client.download_file(self.bucket, key, str(path))

    def list_objects(self, prefix: str) -> list[StoredObject]:
        return _list(self.client, self.bucket, prefix)

    def delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), 1000):
            chunk = [{"Key": key} for key in keys[start : start + 1000]]
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": chunk, "Quiet": True})


class AppFiles:
    """Read side of the app's own file storage (driver documents, avatars) for the mirror."""

    def __init__(self, client: BaseClient) -> None:
        self.client = client

    def list_objects(self, prefix: str) -> list[StoredObject]:
        return _list(self.client, settings.AWS_S3_BUCKET, prefix)

    def get(self, key: str, path: Path) -> None:
        self.client.download_file(settings.AWS_S3_BUCKET, key, str(path))


@lru_cache
def backup_store() -> BackupStore:
    return S3BackupStore()
