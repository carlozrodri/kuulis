from kuulis.core import storage


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
