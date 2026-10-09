from fastapi import APIRouter, Query

from apps.files.schemas import DownloadResponse, UploadRequest, UploadResponse
from apps.users.dependencies import CurrentUser
from kuulis.core import storage
from kuulis.core.exceptions import AppError, PermissionDeniedError
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
async def presign_upload(data: UploadRequest, user: CurrentUser) -> UploadResponse:
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


@router.get("/download", response_model=DownloadResponse)
async def presign_download(user: CurrentUser, key: str = Query(max_length=512)) -> DownloadResponse:
    owner_segment = f"/{user.id}/"
    if owner_segment not in key and not user.can_access_admin:
        raise PermissionDeniedError()
    return DownloadResponse(
        url=storage.presigned_download(key), expires_in=settings.STORAGE_PRESIGN_TTL_SECONDS
    )
