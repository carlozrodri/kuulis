# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "pyotp>=2.9"]
# ///
"""End-to-end smoke test against a deployed environment (QA by default).

Runs the main flow the way the apps do: a passenger and a driver register, the driver fills in
the profile and documents, staff approves, the driver goes online, the passenger quotes and
requests a ride, the driver accepts, arrives, starts and completes it, both rate each other. Both
accounts are flagged as test accounts (left out of metrics) and closed at the end, even if a step
fails.

Needs a running worker (it sends the ride offer). Run after every deploy to QA:

    SMOKE_ADMIN_EMAIL=... SMOKE_ADMIN_PASSWORD=... SMOKE_ADMIN_TOTP_SECRET=... \
        uv run scripts/smoke_e2e.py
    uv run scripts/smoke_e2e.py --base-url https://kuulis-qa.top8.uk

The admin must have the `admin` role (flagging test accounts is admin-only) and its 2FA set up:
SMOKE_ADMIN_TOTP_SECRET is the key shown under the QR when setting it up (a dedicated smoke
account is best). Exit code 0 means every
step passed. Never point it at production without a reason: it creates real rows there.
"""

import argparse
import os
import secrets
import string
import sys
import time
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pyotp

# A spot inside the Caracas service area; the driver waits right at the pickup so the dispatcher
# offers the ride to them before any real driver nearby.
PICKUP = {"lat": 10.4900, "lng": -66.8800, "address": "Plaza Altamira (smoke)"}
DROPOFF = {"lat": 10.5000, "lng": -66.8500, "address": "Los Dos Caminos (smoke)"}
PASSWORD = "Smoke-" + secrets.token_urlsafe(16)
random = secrets.SystemRandom()
# Smallest valid JPEG (1x1 px): enough for storage, the admin only looks at it in this test.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912"
    "130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001"
    "000101011100ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b51000020103"
    "03020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f024336272"
    "82090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475"
    "767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9"
    "cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9"
)


class SmokeError(Exception):
    pass


class Api:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.http = httpx.Client(base_url=f"{base_url.rstrip('/')}/api/v1", timeout=30)
        self.token = token
        self.user_id: str | None = None

    def call(self, method: str, path: str, expect: int | tuple[int, ...] = (200, 201, 204), **kw):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = self.http.request(method, path, headers=headers, **kw)
        expected = (expect,) if isinstance(expect, int) else expect
        if response.status_code not in expected:
            raise SmokeError(f"{method} {path} → {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else None


def step(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        def run(*args: Any, **kwargs: Any) -> Any:
            started = time.monotonic()
            print(f"… {name}", flush=True)
            result = fn(*args, **kwargs)
            print(f"✓ {name} ({time.monotonic() - started:.1f} s)", flush=True)
            return result

        return run

    return wrap


def wait_for(what: str, check: Callable[[], Any], timeout: float, every: float = 2.0) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(every)
    raise SmokeError(f"Timed out after {timeout:.0f} s waiting for {what}")


@step("Register passenger and driver")
def register(base_url: str, stamp: str) -> tuple[Api, Api]:
    users = []
    for who in ("passenger", "driver"):
        api = Api(base_url)
        body = api.call(
            "POST",
            "/auth/register",
            json={
                "email": f"smoke+{who}-{stamp}@example.com",
                "password": PASSWORD,
                "full_name": f"Smoke {who.capitalize()}",
                "accept_legal": True,
            },
        )
        api.token = body["access_token"]
        api.user_id = body["user"]["id"]
        if who == "driver":  # drivers also accept their terms and the wallet conditions (doc 07)
            api.call("POST", "/legal/accept", json={"kinds": ["driver_terms", "wallet"]})
        users.append(api)
    return users[0], users[1]


@step("Flag both accounts as test accounts")
def flag(admin: Api, *apis: Api) -> None:
    for api in apis:
        admin.call("PATCH", f"/users/{api.user_id}", json={"is_test_account": True})


@step("Driver profile, vehicle and documents")
def onboard(driver: Api) -> str:
    digits = "".join(random.choices(string.digits, k=8))
    driver.call(
        "PUT",
        "/drivers/me",
        json={
            "birth_date": str(date(1990, 1, 15)),
            "national_id": f"V{digits}",
            "rif": f"V{digits}0",
            "phone": f"+58412{digits[:7]}",
        },
    )
    plate = "SM" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    driver.call(
        "PUT",
        "/drivers/me/vehicle",
        json={
            "type": "moto",
            "brand": "Smoke",
            "model": "Test 125",
            "year": date.today().year - 1,
            "plate": plate,
            "color": "Negra",
        },
    )
    config = driver.call("GET", "/config/public")
    kinds = [k for k in config["driver_required_documents"] if k != "vehicle_photo"]
    kinds += ["vehicle_photo"] * max(1, config.get("vehicle_photo_min_count", 1))
    for i, kind in enumerate(kinds):
        presign = driver.call(
            "POST",
            "/drivers/me/documents/presign",
            json={
                "kind": kind,
                "filename": f"{kind}-{i}.jpg",
                "content_type": "image/jpeg",
                "size": len(JPEG),
            },
        )
        headers = {"Content-Type": "image/jpeg", **presign.get("headers", {})}
        upload = httpx.request(
            presign.get("method", "PUT"), presign["upload_url"], content=JPEG, headers=headers
        )
        if upload.status_code >= 300:
            raise SmokeError(f"Upload of {kind} failed: {upload.status_code} {upload.text[:300]}")
        driver.call("POST", "/drivers/me/documents", json={"kind": kind, "key": presign["key"]})
    profile = driver.call("POST", "/drivers/me/submit")
    if profile["status"] != "pending_review":
        raise SmokeError(f"Driver status after submit is {profile['status']}")
    return profile["id"]


@step("Staff approves the driver")
def approve(admin: Api, profile_id: str) -> None:
    admin.call("POST", f"/admin/drivers/{profile_id}/approve")


def send_location(driver: Api) -> None:
    driver.call("POST", "/drivers/me/location", json={"lat": PICKUP["lat"], "lng": PICKUP["lng"]})


@step("Driver goes online")
def go_online(driver: Api) -> None:
    driver.call("POST", "/drivers/me/online", json={"lat": PICKUP["lat"], "lng": PICKUP["lng"]})


@step("Passenger quotes and requests a ride")
def request_ride(passenger: Api) -> str:
    quote = passenger.call(
        "POST", "/rides/quote", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"}
    )
    ride = passenger.call(
        "POST", "/rides", json={"quote_id": quote["quote_id"], "payment_method": "cash_usd"}
    )
    if ride["status"] != "searching":
        raise SmokeError(f"New ride status is {ride['status']}")
    return ride["id"]


@step("Driver receives the offer and accepts")
def accept(driver: Api, ride_id: str) -> None:
    def offered() -> bool:
        send_location(driver)  # keeps the driver fresh, like the app does every few seconds
        offer = driver.call("GET", "/drivers/me/state").get("current_offer")
        return bool(offer and offer["ride_id"] == ride_id)

    wait_for("the ride offer (is the worker running?)", offered, timeout=90, every=3)
    driver.call("POST", f"/rides/{ride_id}/accept")


@step("Arrive, start and complete the ride")
def drive(driver: Api, passenger: Api, ride_id: str) -> None:
    for action, status in (
        ("arrive", "driver_arrived"),
        ("start", "in_progress"),
        ("complete", "completed"),
    ):
        ride = driver.call("POST", f"/rides/{ride_id}/{action}")
        if ride["status"] != status:
            raise SmokeError(f"After {action} the ride is {ride['status']}, expected {status}")
    seen = passenger.call("GET", f"/rides/{ride_id}")
    if seen["status"] != "completed":
        raise SmokeError(f"Passenger sees status {seen['status']}")


@step("Both sides rate")
def rate(passenger: Api, driver: Api, ride_id: str) -> None:
    for api in (passenger, driver):
        api.call("POST", f"/rides/{ride_id}/rating", json={"stars": 5, "tags": []})
    if passenger.call("GET", "/rides/pending-rating") is not None:
        raise SmokeError("Passenger still has a ride to rate")


def cleanup(passenger: Api | None, driver: Api | None, ride_id: str | None) -> None:
    """Best effort: never hides the original failure."""
    for api, role in ((passenger, "passenger"), (driver, "driver")):
        if api is None:
            continue
        if ride_id:
            api.call("POST", f"/rides/{ride_id}/cancel", expect=(200, 400, 403, 404, 409, 422))
        if role == "driver":
            api.call("POST", "/drivers/me/offline", expect=(200, 204, 403, 404, 409))
        api.call("DELETE", "/users/me", expect=(200, 202, 204, 401, 409))
    print("✓ Cleanup: accounts closed", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--base-url", default=os.environ.get("SMOKE_BASE_URL", "https://kuulis-qa.top8.uk")
    )
    args = parser.parse_args()
    email = os.environ.get("SMOKE_ADMIN_EMAIL")
    password = os.environ.get("SMOKE_ADMIN_PASSWORD")
    if not email or not password:
        print("Set SMOKE_ADMIN_EMAIL and SMOKE_ADMIN_PASSWORD (an admin account).", file=sys.stderr)
        return 2

    print(f"Smoke test against {args.base_url}", flush=True)
    admin = Api(args.base_url)
    login = admin.call("POST", "/auth/admin/login", json={"email": email, "password": password})
    if "challenge" in login:  # second factor (docs/deployment.md, "Acceso del equipo")
        secret = os.environ.get("SMOKE_ADMIN_TOTP_SECRET")
        if not secret or login["status"] != "totp_required":
            print("Set SMOKE_ADMIN_TOTP_SECRET (the admin's 2FA key).", file=sys.stderr)
            return 2
        code = pyotp.TOTP(secret).now()
        login = admin.call(
            "POST", "/auth/admin/totp", json={"challenge": login["challenge"], "code": code}
        )
    admin.token = login["access_token"]
    stamp = time.strftime("%Y%m%d%H%M%S")
    passenger = driver = None
    ride_id = None
    started = time.monotonic()
    try:
        passenger, driver = register(args.base_url, stamp)
        flag(admin, passenger, driver)
        profile_id = onboard(driver)
        approve(admin, profile_id)
        go_online(driver)
        ride_id = request_ride(passenger)
        accept(driver, ride_id)
        drive(driver, passenger, ride_id)
        rate(passenger, driver, ride_id)
        ride_id = None  # finished: nothing to cancel
    except (SmokeError, httpx.HTTPError) as error:
        print(f"✗ {error}", file=sys.stderr, flush=True)
        cleanup(passenger, driver, ride_id)
        return 1
    cleanup(passenger, driver, ride_id)
    print(f"Smoke test passed in {time.monotonic() - started:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
