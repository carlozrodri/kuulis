import base64
import json
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from apps.updates import services
from kuulis.core import storage
from kuulis.settings import settings

API = "/api/v1"
PREFIX = f"updates/{settings.APP_ENV}/"
RUNTIME = "4f1c0ffee"


def _asset(name: str, content_type: str, ext: str | None = None) -> dict:
    return {
        "s3_key": f"{PREFIX}assets/{name}",
        "hash": f"hash-{name}",
        "key": f"key-{name}",
        "contentType": content_type,
        "fileExtension": ext,
    }


def _candidate(n: int, runtime: str = RUNTIME) -> dict:
    return {
        "platform": "android",
        "runtime_version": runtime,
        "commit": f"abc{n}",
        "message": f"Cambio {n}",
        "built_at": datetime.now(UTC).isoformat(),
        "bundle_size": 3_000_000,
        "launch_asset": _asset(f"bundle{n}", "application/javascript"),
        "assets": [_asset("logo", "image/png", ".png")],
        "extra": {"expoClient": {"name": "Kuulis (QA)", "extra": {"apiUrl": "https://x/api/v1"}}},
    }


@pytest.fixture
def bucket(monkeypatch) -> dict[str, dict]:
    files: dict[str, dict] = {}

    def list_objects(prefix: str, limit: int = 200):
        keys = sorted((k for k in files if k.startswith(prefix)), reverse=True)
        return [{"Key": k, "Size": 1} for k in keys][:limit]

    monkeypatch.setattr(storage, "list_objects", list_objects)
    monkeypatch.setattr(
        storage, "get_object_bytes", lambda key, **_: json.dumps(files[key]).encode()
    )
    monkeypatch.setattr(
        storage, "presigned_download", lambda key, expires_in=None: f"https://s3.test/{key}"
    )
    services._cache.clear()
    return files


@pytest.fixture
def signing_key(monkeypatch) -> rsa.RSAPublicKey:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    # Coolify single-line values: newlines written as "\n".
    monkeypatch.setattr(settings, "UPDATES_SIGNING_KEY", pem.replace("\n", "\\n"))
    return key.public_key()


def _add(bucket: dict, n: int, **kwargs) -> str:
    key = f"{PREFIX}candidates/2026101{n}-src{n}.json"
    bucket[key] = _candidate(n, **kwargs)
    return key


async def _publish(client, headers, key: str, **extra) -> dict:
    response = await client.post(
        f"{API}/admin/app/updates",
        json={"candidate_key": key, "channel": "qa", **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _headers(client_id: str = "device-1", runtime: str = RUNTIME, signed: bool = True) -> dict:
    headers = {
        "expo-protocol-version": "1",
        "expo-platform": "android",
        "expo-runtime-version": runtime,
        "expo-channel-name": "qa",
        "eas-client-id": client_id,
        "accept": "multipart/mixed,application/expo+json,application/json",
    }
    if signed:
        headers["expo-expect-signature"] = 'sig, keyid="main", alg="rsa-v1_5-sha256"'
    return headers


def _parts(response) -> dict[str, tuple[dict, bytes]]:
    """{name: (part headers, body)} of a multipart/mixed response."""
    boundary = response.headers["content-type"].split("boundary=")[1]
    parts = {}
    for chunk in response.content.split(f"--{boundary}".encode())[1:-1]:
        head, body = chunk.strip(b"\r\n").split(b"\r\n\r\n", 1)
        headers = dict(line.split(": ", 1) for line in head.decode().split("\r\n"))
        name = headers["content-disposition"].split('name="')[1].rstrip('"')
        parts[name] = (headers, body)
    return parts


def _verify(public_key: rsa.RSAPublicKey, signature_header: str, body: bytes) -> None:
    fields = dict(item.strip().split("=", 1) for item in signature_header.split(","))
    assert fields["keyid"] == '"main"'
    sig = base64.b64decode(fields["sig"].strip('"'))
    public_key.verify(sig, body, padding.PKCS1v15(), hashes.SHA256())


async def _manifest(client, **kwargs):
    return await client.get(f"{API}/updates/manifest", headers=_headers(**kwargs))


async def test_signed_manifest_for_the_runtime(client, admin_headers, bucket, signing_key) -> None:
    assert (await client.get(f"{API}/updates/manifest")).status_code == 400
    empty = await _manifest(client)
    assert empty.status_code == 204 and empty.headers["expo-protocol-version"] == "1"

    candidates = (
        await client.get(f"{API}/admin/app/update-candidates", headers=admin_headers)
    ).json()
    assert candidates == []
    key = _add(bucket, 1)
    listed = (await client.get(f"{API}/admin/app/update-candidates", headers=admin_headers)).json()
    assert listed[0]["key"] == key and listed[0]["asset_count"] == 2
    update = await _publish(client, admin_headers, key)
    assert update["message"] == "Cambio 1" and update["rollout_percent"] == 100
    again = await client.post(
        f"{API}/admin/app/updates",
        json={"candidate_key": key, "channel": "qa"},
        headers=admin_headers,
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "update_exists"

    response = await _manifest(client)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("multipart/mixed; boundary=")
    assert response.headers["cache-control"] == "private, max-age=0"
    part_headers, body = _parts(response)["manifest"]
    _verify(signing_key, part_headers["expo-signature"], body)
    manifest = json.loads(body)
    assert manifest["id"] == update["id"] and manifest["runtimeVersion"] == RUNTIME
    assert manifest["createdAt"].endswith("Z")
    assert manifest["launchAsset"] == {
        "hash": "hash-bundle1",
        "key": "key-bundle1",
        "contentType": "application/javascript",
        "url": f"https://s3.test/{PREFIX}assets/bundle1",
    }
    assert manifest["assets"][0]["fileExtension"] == ".png"
    assert manifest["extra"]["expoClient"]["extra"]["apiUrl"] == "https://x/api/v1"

    # Another native build (runtime) or channel gets nothing.
    assert (await _manifest(client, runtime="other")).status_code == 204
    other = {**_headers(), "expo-channel-name": "production"}
    assert (await client.get(f"{API}/updates/manifest", headers=other)).status_code == 204

    # Apps without code signing get the same manifest unsigned.
    unsigned = _parts(await _manifest(client, signed=False))["manifest"]
    assert "expo-signature" not in unsigned[0]


async def test_rollout_reaches_a_stable_share(client, admin_headers, bucket, signing_key) -> None:
    first = await _publish(client, admin_headers, _add(bucket, 1))
    second = await _publish(client, admin_headers, _add(bucket, 2), rollout_percent=10)

    async def served(client_id: str) -> str:
        return json.loads(_parts(await _manifest(client, client_id=client_id))["manifest"][1])["id"]

    ids = [await served(f"device-{i}") for i in range(200)]
    share = ids.count(second["id"]) / len(ids)
    assert 0.03 < share < 0.2, share
    assert set(ids) == {first["id"], second["id"]}
    assert await served("device-7") == await served("device-7")  # stable per device

    paused = await client.patch(
        f"{API}/admin/app/updates/{second['id']}",
        json={"rollout_percent": 0},
        headers=admin_headers,
    )
    assert paused.json()["rollout_percent"] == 0
    assert {await served(f"device-{i}") for i in range(30)} == {first["id"]}


async def test_revert_publishes_a_newer_copy_or_the_apk_code(
    client, admin_headers, bucket, signing_key
) -> None:
    first = await _publish(client, admin_headers, _add(bucket, 1))
    second = await _publish(client, admin_headers, _add(bucket, 2))

    reverted = await client.post(
        f"{API}/admin/app/updates/{second['id']}/revert", headers=admin_headers
    )
    assert reverted.status_code == 201, reverted.text
    copy = reverted.json()
    assert copy["kind"] == "update" and copy["reverted_from_id"] == second["id"]
    assert copy["commit"] == "abc1" and copy["created_at"] > second["created_at"]
    manifest = json.loads(_parts(await _manifest(client))["manifest"][1])
    assert manifest["id"] == copy["id"] and manifest["launchAsset"]["key"] == "key-bundle1"

    twice = await client.post(
        f"{API}/admin/app/updates/{second['id']}/revert", headers=admin_headers
    )
    assert twice.status_code == 409

    # Reverting the copy leaves nothing before it: back to the code inside the APK.
    back = await client.post(f"{API}/admin/app/updates/{copy['id']}/revert", headers=admin_headers)
    assert back.json()["kind"] == "rollback"
    part_headers, body = _parts(await _manifest(client))["directive"]
    _verify(signing_key, part_headers["expo-signature"], body)
    assert json.loads(body)["type"] == "rollBackToEmbedded"

    history = (await client.get(f"{API}/admin/app/updates", headers=admin_headers)).json()
    assert [u["withdrawn_at"] is None for u in history] == [True, False, False, False]
    assert first["id"] in {u["id"] for u in history}


async def test_unsafe_candidates_are_refused(client, admin_headers, bucket) -> None:
    outside = f"{PREFIX}candidates/evil.json"
    bucket[outside] = {**_candidate(1), "launch_asset": {**_asset("x", "a/b"), "s3_key": "qa/x"}}
    for key in (outside, "builds/qa/kuulis-1.json", f"{PREFIX}candidates/../x.json"):
        bucket.setdefault(key, _candidate(1))
        response = await client.post(
            f"{API}/admin/app/updates",
            json={"candidate_key": key, "channel": "qa"},
            headers=admin_headers,
        )
        assert response.status_code == 404, key
        assert response.json()["error"]["code"] == "update_candidate_not_found"


async def test_signed_requests_need_the_key(client, admin_headers, bucket, monkeypatch) -> None:
    monkeypatch.setattr(settings, "UPDATES_SIGNING_KEY", "")
    await _publish(client, admin_headers, _add(bucket, 1))
    response = await _manifest(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "updates_signing_disabled"


async def test_usage_counts_users_per_update(client, admin_headers, user_headers) -> None:
    update_id = "0b6f0a39-5a2d-4f53-9f52-3b1a6f2c9a10"
    android = {"X-App-Platform": "android", "X-App-Update": update_id}
    await client.get(f"{API}/users/me", headers={**user_headers, **android})
    await client.get(f"{API}/users/me", headers={**admin_headers, **android})
    await client.get(f"{API}/users/me", headers={**admin_headers, "X-App-Update": "embedded"})
    await client.get(
        f"{API}/users/me",
        headers={**admin_headers, "X-App-Platform": "android", "X-App-Update": "nope"},
    )
    usage = (await client.get(f"{API}/admin/app/update-usage", headers=admin_headers)).json()
    assert usage == [{"update_id": update_id, "users": 2}]
