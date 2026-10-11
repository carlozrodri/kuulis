import json
from datetime import UTC, datetime

import pytest

from apps.rides.tests.conftest import NEAR, go_online, make_driver
from apps.users.models import Role
from conftest import _login, _make_user, make_staff_role
from kuulis.core import storage
from kuulis.settings import settings

API = "/api/v1"
PREFIX = f"builds/{settings.APP_ENV}/"


def _meta(build: int, version: str = "1.0.0") -> dict:
    name = f"kuulis-{settings.APP_ENV}-qa-{build}.apk"
    return {
        "file_name": name,
        "version": version,
        "build": build,
        "size": 61_000_000 + build,
        "sha256": "a" * 64,
        "md5": "b" * 32,
        "profile": "qa",
        "built_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def bucket(monkeypatch) -> dict[str, dict]:
    """A fake bucket with the compiler's metadata files; never touches real storage."""
    files: dict[str, dict] = {}

    def list_objects(prefix: str, limit: int = 200):
        keys = sorted((k for k in files if k.startswith(prefix)), key=lambda k: -files[k]["build"])
        return [{"Key": k, "Size": 1, "LastModified": files[k]["build"]} for k in keys][:limit]

    monkeypatch.setattr(storage, "list_objects", list_objects)
    monkeypatch.setattr(
        storage, "get_object_bytes", lambda key, **_: json.dumps(files[key]).encode()
    )
    monkeypatch.setattr(
        storage, "presigned_download", lambda key, expires_in=None: f"https://s3.test/{key}"
    )
    return files


def _add(bucket: dict, build: int) -> str:
    key = f"{PREFIX}kuulis-{build}.json"
    bucket[key] = _meta(build)
    return key


async def _publish(client, headers, key: str, **extra) -> dict:
    response = await client.post(
        f"{API}/admin/app/releases",
        json={"build_key": key, "channel": "qa", **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_publish_and_version_check(client, admin_headers, bucket) -> None:
    first = _add(bucket, 3)
    second = _add(bucket, 5)

    builds = (await client.get(f"{API}/admin/app/builds", headers=admin_headers)).json()
    assert [b["build"] for b in builds] == [5, 3]
    assert builds[0]["published_channels"] == []

    nothing = (await client.get(f"{API}/app/version", params={"build": 3})).json()
    assert nothing == {
        "latest": None,
        "minimum_build": 0,
        "update_available": False,
        "update_required": False,
    }
    assert (await client.get(f"{API}/app/download")).status_code == 404

    await _publish(client, admin_headers, first)
    release = await _publish(client, admin_headers, second, notes="Mapa más rápido")
    assert release["file_key"] == f"{PREFIX}kuulis-{settings.APP_ENV}-qa-5.apk"
    again = await client.post(
        f"{API}/admin/app/releases",
        json={"build_key": second, "channel": "qa"},
        headers=admin_headers,
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "release_exists"

    check = (await client.get(f"{API}/app/version", params={"build": 3})).json()
    assert check["latest"]["build"] == 5 and check["latest"]["notes"] == "Mapa más rápido"
    assert check["latest"]["download_url"] == f"https://s3.test/{release['file_key']}"
    assert check["update_available"] is True and check["update_required"] is False
    assert (await client.get(f"{API}/app/version", params={"build": 5})).json()[
        "update_available"
    ] is False

    download = await client.get(f"{API}/app/download")
    assert download.status_code == 302 and download.headers["location"].endswith(".apk")

    # Withdrawing the newest offers the previous one again.
    withdrawn = await client.patch(
        f"{API}/admin/app/releases/{release['id']}", json={"withdrawn": True}, headers=admin_headers
    )
    assert withdrawn.status_code == 200 and withdrawn.json()["withdrawn_at"]
    assert (await client.get(f"{API}/app/version")).json()["latest"]["build"] == 3

    # A withdrawn build can be published again.
    await _publish(client, admin_headers, second)


async def test_build_keys_outside_the_folder_are_refused(client, admin_headers, bucket) -> None:
    bucket["qa/files/secret.json"] = _meta(9)
    response = await client.post(
        f"{API}/admin/app/releases",
        json={"build_key": "qa/files/secret.json", "channel": "qa"},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "build_not_found"


async def test_mandatory_release_blocks_old_builds_on_rides(client, admin_headers, bucket) -> None:
    key = _add(bucket, 7)
    release = await _publish(client, admin_headers, key, is_mandatory=True)
    check = (await client.get(f"{API}/app/version", params={"build": 6})).json()
    assert check["minimum_build"] == 7 and check["update_required"] is True

    driver = await make_driver(client, "old-app@example.com", "Luis")
    old = {**driver.headers, "X-App-Platform": "android", "X-App-Build": "6", "X-App-Channel": "qa"}
    blocked = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=old
    )
    assert blocked.status_code == 426, blocked.text
    assert blocked.json()["error"] == {
        "code": "app_update_required",
        "message": blocked.json()["error"]["message"],
        "details": {"minimum_build": 7},
    }
    # Other screens keep working, and apps that send no build are let through.
    assert (await client.get(f"{API}/users/me", headers=old)).status_code == 200
    await go_online(client, driver, NEAR)

    # Making it optional again lifts the block.
    await client.patch(
        f"{API}/admin/app/releases/{release['id']}",
        json={"is_mandatory": False},
        headers=admin_headers,
    )
    ok = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=old
    )
    assert ok.status_code == 200, ok.text


async def test_usage_counts_distinct_users_per_build(client, admin_headers, user_headers) -> None:
    android = {"X-App-Platform": "android", "X-App-Build": "12"}
    for _ in range(3):
        await client.get(f"{API}/users/me", headers={**user_headers, **android})
    await client.get(f"{API}/users/me", headers={**admin_headers, **android})
    await client.get(f"{API}/users/me", headers={**admin_headers, "X-App-Build": "nope"})
    usage = (await client.get(f"{API}/admin/app/usage", headers=admin_headers)).json()
    assert usage == [{"platform": "android", "build": 12, "users": 2}]


async def test_staff_need_the_permission(client, bucket) -> None:
    role = await make_staff_role("soporte_test", {"users.view"})
    await _make_user("support@example.com", Role.STAFF, role)
    headers = await _login(client, "support@example.com")
    assert (await client.get(f"{API}/admin/app/releases", headers=headers)).status_code == 403
    response = await client.post(
        f"{API}/admin/app/releases",
        json={"build_key": _add(bucket, 4), "channel": "qa"},
        headers=headers,
    )
    assert response.status_code == 403
