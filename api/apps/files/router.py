from fastapi import APIRouter, Query, Request

from apps.files.schemas import DownloadResponse, UploadRequest, UploadResponse
from apps.users.dependencies import CurrentUser, has_admin_session
from kuulis.core import storage
from kuulis.core.exceptions import AppError, PermissionDeniedError
from kuulis.core.rate_limit import limiter
from kuulis.settings import settings

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}


@router.post("/presign-upload", response_model=UploadResponse)
@limiter.limit("30/hour")
async def presign_upload(
    request: Request, data: UploadRequest, user: CurrentUser
) -> UploadResponse:
    """Returns a presigned URL; the client uploads straight to S3 (the API never proxies bytes)."""
    if data.content_type not in ALLOWED_TYPES:
        raise AppError("File type not allowed", code="file_type_not_allowed")
    if data.size > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("File too large", code="file_too_large")
    key = storage.build_key(f"{data.folder}/{user.id}", data.filename)
    return UploadResponse(
        key=key,
        upload_url=storage.presigned_upload(key, data.content_type),
        headers={"Content-Type": data.content_type},
        expires_in=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )


# Folders whose second level is the owner's id: <prefix>/<folder>/<user id>/...
OWNED_FOLDERS = ("avatars", "uploads", "drivers")


def _owns(user_id: object, key: str) -> bool:
    return ".." not in key and any(
        key.startswith(storage.folder_prefix(f"{folder}/{user_id}")) for folder in OWNED_FOLDERS
    )


@router.get("/download", response_model=DownloadResponse)
async def presign_download(user: CurrentUser, key: str = Query(max_length=512)) -> DownloadResponse:
    if _owns(user.id, key):
        ttl = settings.STORAGE_PRESIGN_TTL_SECONDS
    elif has_admin_session(user):
        ttl = settings.PRIVATE_FILE_URL_SECONDS  # someone else's file: short-lived link
    else:
        raise PermissionDeniedError()
    return DownloadResponse(url=storage.presigned_download(key, ttl), expires_in=ttl)
