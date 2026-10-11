"""Removes EXIF (GPS position, device, date) from uploaded photos: driver selfies and documents,
vehicle photos and avatars. Uploads go straight from the phone to S3, so a worker task reads the
object afterwards, re-encodes it without metadata (keeping its orientation) and writes it back
under the same key."""

import asyncio
import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

from kuulis.core import storage
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
MAX_PIXELS = 64_000_000  # 64 MP covers phone cameras; bigger is skipped, not decoded


def strip_metadata(data: bytes, content_type: str) -> bytes | None:
    """The image without metadata, or None when there was nothing to remove (or not an image
    Pillow reads: PDF, HEIC)."""
    image_format = FORMATS.get(content_type)
    if image_format is None:
        return None
    try:
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, Image.DecompressionBombError):
        return None
    with image:
        if image.width * image.height > MAX_PIXELS:
            return None
        if not image.getexif() and not image.info.get("exif") and not image.info.get("xmp"):
            return None
        upright = ImageOps.exif_transpose(image)  # the rotation lives in the EXIF we drop
        output = io.BytesIO()
        options = {"quality": 90} if image_format in ("JPEG", "WEBP") else {}
        upright.save(output, format=image_format, **options)  # no exif= → no metadata
        return output.getvalue()


def _strip_object(key: str) -> bool:
    client = storage.get_s3_client()
    found = client.get_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    content_type = str(found.get("ContentType", "")).split(";")[0].strip().lower()
    if content_type not in FORMATS:
        found["Body"].close()
        return False
    if int(found.get("ContentLength") or 0) > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        found["Body"].close()  # bigger than any upload we presign: don't load it into memory
        logger.warning("Skipped the metadata clean-up of %s: too large", key)
        return False
    cleaned = strip_metadata(found["Body"].read(), content_type)
    if cleaned is None:
        return False
    client.put_object(
        Bucket=settings.AWS_S3_BUCKET, Key=key, Body=cleaned, ContentType=content_type
    )
    return True


@broker.task(task_name="files.strip_metadata", retry_on_error=True, max_retries=3)
async def strip_object_metadata(key: str) -> bool:
    if not settings.storage_enabled:
        return False
    stripped = await asyncio.to_thread(_strip_object, key)
    if stripped:
        logger.info("Removed photo metadata from %s", key)
    return stripped


async def schedule(key: str) -> None:
    """Queues the clean-up; never fails the request that registered the photo."""
    try:
        await strip_object_metadata.kiq(key)
    except Exception:
        logger.warning("Could not queue the metadata clean-up of %s", key, exc_info=True)
