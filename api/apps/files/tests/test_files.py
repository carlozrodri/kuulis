import io

from PIL import Image

from apps.files.metadata import strip_metadata
from kuulis.core import storage
from kuulis.settings import settings


async def test_presign_rejects_disallowed_type(client, user_headers):
    response = await client.post(
        "/api/v1/files/presign-upload",
        json={"filename": "x.exe", "content_type": "application/x-msdownload", "size": 10},
        headers=user_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "file_type_not_allowed"


async def test_presign_upload(client, user_headers, monkeypatch):
    monkeypatch.setattr(storage, "presigned_upload", lambda key, ct: f"https://s3.test/{key}")
    response = await client.post(
        "/api/v1/files/presign-upload",
        json={
            "filename": "my photo.png",
            "content_type": "image/png",
            "size": 1024,
            "folder": "avatars",
        },
        headers=user_headers,
    )
    assert response.status_code == 200
    key = response.json()["key"]
    assert key.startswith("test/avatars/") and key.endswith("-my-photo.png")


def test_build_key_sanitizes_names():
    key = storage.build_key("uploads/u1", "../../etc/passwd")
    assert ".." not in key.split("/")[-1].split("-", 1)[0]
    assert "/" not in key.split("/")[-1]


async def _user_id(client, headers) -> str:
    return (await client.get("/api/v1/users/me", headers=headers)).json()["id"]


async def test_download_own_file_and_admin_short_link(
    client, user_headers, admin_headers, monkeypatch
):
    calls = []

    def fake_download(key, expires_in=None):
        calls.append(expires_in)
        return f"https://s3.test/get/{key}"

    monkeypatch.setattr(storage, "presigned_download", fake_download)
    key = storage.folder_prefix(f"drivers/{await _user_id(client, user_headers)}") + "selfie.jpg"

    own = await client.get("/api/v1/files/download", params={"key": key}, headers=user_headers)
    assert own.status_code == 200, own.text
    assert own.json()["expires_in"] == settings.STORAGE_PRESIGN_TTL_SECONDS

    staff_view = await client.get(
        "/api/v1/files/download", params={"key": key}, headers=admin_headers
    )
    assert staff_view.status_code == 200
    assert staff_view.json()["expires_in"] == settings.PRIVATE_FILE_URL_SECONDS <= 300
    assert calls == [settings.STORAGE_PRESIGN_TTL_SECONDS, settings.PRIVATE_FILE_URL_SECONDS]


async def test_download_rejects_someone_elses_file(client, user_headers, admin_headers):
    other = storage.folder_prefix(f"drivers/{await _user_id(client, admin_headers)}") + "id.jpg"
    response = await client.get(
        "/api/v1/files/download", params={"key": other}, headers=user_headers
    )
    assert response.status_code == 403

    own_prefix = storage.folder_prefix(f"avatars/{await _user_id(client, user_headers)}")
    escape = await client.get(
        "/api/v1/files/download",
        params={"key": f"{own_prefix}../../drivers/x/id.jpg"},
        headers=user_headers,
    )
    assert escape.status_code == 403


def _jpeg_with_gps() -> bytes:
    image = Image.new("RGB", (40, 20), "red")
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotated 90°
    exif[0x010F] = "PhoneMaker"
    exif.get_ifd(0x8825)[2] = (10.0, 30.0, 0.0)  # GPSLatitude
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def test_strip_metadata_removes_exif_and_keeps_orientation():
    original = _jpeg_with_gps()
    with Image.open(io.BytesIO(original)) as before:
        assert before.getexif()

    cleaned = strip_metadata(original, "image/jpeg")

    assert cleaned is not None
    with Image.open(io.BytesIO(cleaned)) as after:
        assert not after.getexif()
        assert "exif" not in after.info
        assert after.size == (20, 40)  # rotated upright before dropping the tag


def test_strip_metadata_skips_clean_images_and_other_types():
    output = io.BytesIO()
    Image.new("RGB", (4, 4)).save(output, format="PNG")
    assert strip_metadata(output.getvalue(), "image/png") is None
    assert strip_metadata(b"%PDF-1.7", "application/pdf") is None
    assert strip_metadata(b"...", "image/heic") is None
    assert strip_metadata(b"not an image", "image/jpeg") is None
