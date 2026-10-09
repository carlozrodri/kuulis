from apps.config import services
from kuulis.core.cache import cache_get

DEFAULTS = {
    "driver_min_age": 21,
    "vehicle_min_year": {"moto": 2013, "car": 1993},
    "enabled_vehicle_types": ["moto"],
    "driver_required_documents": [
        "id_card",
        "rif",
        "drivers_license",
        "medical_certificate",
        "vehicle_registration",
        "selfie",
        "vehicle_photo",
    ],
    "vehicle_photo_min_count": 2,
}


async def test_public_config_returns_defaults_and_caches(client):
    response = await client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json() == DEFAULTS
    assert await cache_get(services.CACHE_KEY) == DEFAULTS


async def test_admin_config_permissions(client, user_headers, staff_headers):
    assert (await client.get("/api/v1/admin/config", headers=user_headers)).status_code == 403
    assert (await client.get("/api/v1/admin/config", headers=staff_headers)).status_code == 200
    response = await client.patch(
        "/api/v1/admin/config", json={"driver_min_age": 25}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_admin_updates_config_and_invalidates_cache(client, admin_headers):
    await client.get("/api/v1/config/public")  # warm the cache
    response = await client.patch(
        "/api/v1/admin/config",
        json={"driver_min_age": 23, "vehicle_min_year": {"moto": 2015}},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["driver_min_age"] == 23
    assert body["vehicle_min_year"] == {"moto": 2015, "car": 1993}
    public = (await client.get("/api/v1/config/public")).json()
    assert public == body

    # The full object (as the admin panel sends it) is accepted too.
    full = body | {"enabled_vehicle_types": ["moto", "car"], "vehicle_photo_min_count": 3}
    response = await client.patch("/api/v1/admin/config", json=full, headers=admin_headers)
    assert response.json() == full


async def test_admin_config_validation(client, admin_headers):
    for payload in (
        {"enabled_vehicle_types": []},
        {"enabled_vehicle_types": ["bike"]},
        {"driver_required_documents": ["selfie", "selfie"]},
        {"driver_min_age": 5},
    ):
        response = await client.patch("/api/v1/admin/config", json=payload, headers=admin_headers)
        assert response.status_code == 422, payload
