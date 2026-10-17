"""Doc 23: ride for someone else, note for the driver, shareable receipt and compliments."""

import io

from PIL import Image
from sqlalchemy import update

from apps.rides import receipt
from apps.rides.models import Rating
from conftest import ride_step
from kuulis.core.db import SessionLocal

from .conftest import DROPOFF, NEAR, PICKUP, go_online, make_driver

API = "/api/v1"
RIDER = {"name": "  María José  ", "phone": "+584141112233"}


async def _request(client, passenger, **extra) -> dict:
    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    assert quote.status_code == 200, quote.text
    response = await client.post(
        f"{API}/rides",
        json={"quote_id": quote.json()["quote_id"], "payment_method": "pago_movil", **extra},
        headers=passenger.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _complete(client, ride_id: str, driver) -> None:
    for step in ("arrive", "start", "complete"):
        response = await ride_step(client, ride_id, step, driver.headers)
        assert response.status_code == 200, response.text


async def test_ride_for_someone_else_with_a_note(client, passenger, recorder, admin_headers):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    ride = await _request(
        client, passenger, note="  Estoy en la puerta\ndel edificio azul ", rider=RIDER
    )
    assert ride["note"] == "Estoy en la puerta del edificio azul"
    assert ride["rider_name"] == "María José"
    assert ride["rider_phone"] == "+584141112233"  # the passenger who requested sees it

    # The driver sees the note and who rides before accepting, but never the phone.
    offer = recorder.of("ride.offer", driver.id)[-1]
    assert offer["note"] == "Estoy en la puerta del edificio azul"
    assert offer["rider_name"] == "María José"
    assert "rider_phone" not in offer
    accepted = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert accepted.json()["rider_name"] == "María José"
    assert accepted.json()["rider_phone"] is None
    to_driver = recorder.of("ride.updated", driver.id)[-1]
    to_passenger = recorder.of("ride.updated", passenger.id)[-1]
    assert to_driver["rider_phone"] is None and to_passenger["rider_phone"] == RIDER["phone"]

    detail = await client.get(f"{API}/admin/rides/{ride['id']}", headers=admin_headers)
    assert detail.json()["rider_phone"] == RIDER["phone"]
    assert detail.json()["note"] == "Estoy en la puerta del edificio azul"

    # The live link for the person riding shows their name and the start PIN.
    shared = await client.post(
        f"{API}/rides/{ride['id']}/share", json={"for_rider": True}, headers=passenger.headers
    )
    assert shared.status_code == 200, shared.text
    page = (await client.get(f"{API}/public/rides/shared/{shared.json()['token']}")).json()
    assert page["for_rider"] is True and page["passenger"]["first_name"] == "María"
    async with SessionLocal() as session:
        from apps.rides.models import Ride

        pin = (await session.get(Ride, ride["id"])).start_pin
    assert page["start_pin"] == pin
    # A plain link (for a trusted contact) never shows the PIN; the driver cannot ask for one.
    plain = await client.post(f"{API}/rides/{ride['id']}/share", headers=passenger.headers)
    page = (await client.get(f"{API}/public/rides/shared/{plain.json()['token']}")).json()
    assert page["for_rider"] is False and page["start_pin"] is None
    refused = await client.post(
        f"{API}/rides/{ride['id']}/share", json={"for_rider": True}, headers=driver.headers
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "ride_not_for_rider"


async def test_note_and_rider_are_validated(client, passenger):
    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    quote_id = quote.json()["quote_id"]
    for extra in (
        {"note": "x" * 141},
        {"rider": {"name": "Ana", "phone": "04141112233"}},
        {"rider": {"name": "   ", "phone": "+584141112233"}},
    ):
        response = await client.post(
            f"{API}/rides",
            json={"quote_id": quote_id, "payment_method": "cash_usd", **extra},
            headers=passenger.headers,
        )
        assert response.status_code == 422, extra
    # A plain ride has neither, and its live link cannot be "for the rider".
    ride = await _request(client, passenger, note="   ")
    assert ride["note"] is None and ride["rider_name"] is None
    refused = await client.post(
        f"{API}/rides/{ride['id']}/share", json={"for_rider": True}, headers=passenger.headers
    )
    assert refused.json()["error"]["code"] == "ride_not_for_rider"


async def test_receipt_image_and_signed_link(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    ride = await _request(client, passenger, rider=RIDER)
    early = await client.get(f"{API}/rides/{ride['id']}/receipt", headers=passenger.headers)
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "receipt_unavailable"

    await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    await _complete(client, ride["id"], driver)
    response = await client.get(f"{API}/rides/{ride['id']}/receipt", headers=passenger.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["number"] == ride["id"].replace("-", "")[:8].upper()
    assert body["total"] == ride["total"] and body["payment_method"] == "pago_movil"
    assert body["passenger_name"] == "María"  # who rode, not the account holder
    assert body["driver_name"] == "Luis" and body["plate"].startswith("AB")
    assert body["pickup_address"] == "Plaza Altamira"
    # The driver can open it too; a stranger cannot.
    assert (
        await client.get(f"{API}/rides/{ride['id']}/receipt", headers=driver.headers)
    ).status_code == 200
    stranger = await make_driver(client, "otro@example.com", "Otro")
    assert (
        await client.get(f"{API}/rides/{ride['id']}/receipt", headers=stranger.headers)
    ).status_code == 404

    path = body["image_url"].split("/api/v1", 1)[1]
    image = await client.get(f"{API}{path}")  # no login
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    png = Image.open(io.BytesIO(image.content))
    assert png.width == 1080 and 1200 < png.height < 2600

    token = path.rsplit("/", 1)[1].removesuffix(".png")
    english = receipt.token_for(receipt.parse_token(token)[0], "en")
    assert (await client.get(f"{API}/public/rides/receipts/{english}.png")).status_code == 200
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert (await client.get(f"{API}/public/rides/receipts/{forged}.png")).status_code == 404
    assert (await client.get(f"{API}/public/rides/receipts/nope.png")).status_code == 404


async def test_compliments_in_driver_stats(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    ride = await _request(client, passenger)
    await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    await _complete(client, ride["id"], driver)
    rated = await client.post(
        f"{API}/rides/{ride['id']}/rating",
        json={"stars": 5, "tags": ["friendly", "clean_helmet", "made_up"]},
        headers=passenger.headers,
    )
    assert rated.status_code == 200, rated.text

    # An instant test ride trips the risk checks, so its rating is ignored: it does not count.
    url = f"{API}/drivers/me/stats"
    assert (await client.get(url, headers=driver.headers)).json()["compliments"] == []
    async with SessionLocal() as session:
        await session.execute(update(Rating).values(ignored=False))
        await session.commit()
    stats = (await client.get(url, headers=driver.headers)).json()
    assert stats["compliments"] == [
        {"tag": "clean_helmet", "count": 1},
        {"tag": "friendly", "count": 1},
    ]
