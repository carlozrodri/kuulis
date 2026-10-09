from apps.config import services
from apps.config.models import AppSetting
from apps.config.schemas import AppConfig
from kuulis.core.cache import cache_get
from kuulis.core.db import SessionLocal

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
    "fares": {
        "moto": {"base": "0.80", "per_km": "0.35", "per_minute": "0.05", "minimum": "1.50"},
        "car": {"base": "1.50", "per_km": "0.60", "per_minute": "0.08", "minimum": "2.50"},
    },
    "surge_rules": [],
    "surge_manual_multiplier": "1.00",
    "fare_rounding": "0.10",
    "payment_methods": ["cash_usd", "pago_movil", "binance", "zelle", "cash_ves"],
    "service_areas": [
        {"name": "Caracas", "min_lat": 10.35, "max_lat": 10.56, "min_lng": -67.1, "max_lng": -66.7}
    ],
    "offer_timeout_seconds": 15,
    "search_radius_m": [2000, 4000, 7000],
    "search_timeout_seconds": 180,
    "quote_ttl_seconds": 300,
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
        {"surge_manual_multiplier": "3.50"},
        {"surge_manual_multiplier": "1.234"},
        {"fare_rounding": "0"},
        {"payment_methods": []},
        {"payment_methods": ["bitcoin"]},
        {"search_radius_m": [4000, 2000]},
        {"service_areas": [{"min_lat": 11, "max_lat": 10, "min_lng": -67, "max_lng": -66}]},
        {"service_areas": []},
        {"surge_rules": [{"days": [7], "start": "07:00", "end": "09:00", "multiplier": "1.2"}]},
        {"surge_rules": [{"days": [0], "start": "7am", "end": "09:00", "multiplier": "1.2"}]},
        {"search_timeout_seconds": 30, "offer_timeout_seconds": 60},
        {"enabled_vehicle_types": ["moto", "car"], "fares": {"car": {"base": "-1"}}},
    ):
        response = await client.patch("/api/v1/admin/config", json=payload, headers=admin_headers)
        assert response.status_code == 422, payload


async def test_admin_updates_ride_config(client, admin_headers):
    response = await client.patch(
        "/api/v1/admin/config",
        json={
            "fares": {"car": {"base": 2, "per_km": "0.7", "per_minute": "0.1", "minimum": "3"}},
            "surge_rules": [
                {"days": [4, 5], "start": "22:00", "end": "02:00", "multiplier": "1.5"}
            ],
            "surge_manual_multiplier": "1.2",
            "payment_methods": ["cash_usd", "zelle"],
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fares"]["car"] == {
        "base": "2.00",
        "per_km": "0.70",
        "per_minute": "0.10",
        "minimum": "3.00",
    }
    assert body["fares"]["moto"] == DEFAULTS["fares"]["moto"]  # merged per vehicle type
    assert body["surge_rules"][0]["multiplier"] == "1.50"
    assert body["surge_manual_multiplier"] == "1.20"
    assert (await client.get("/api/v1/config/public")).json() == body


VALENCIA = {
    "name": "Valencia",
    "min_lat": 39.4,
    "max_lat": 39.55,
    "min_lng": -0.45,
    "max_lng": -0.3,
}


async def test_admin_adds_a_service_area(client, admin_headers):
    areas = [*DEFAULTS["service_areas"], VALENCIA]
    response = await client.patch(
        "/api/v1/admin/config", json={"service_areas": areas}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["service_areas"] == areas
    config = AppConfig.model_validate(response.json())
    assert config.area_at(39.47, -0.376).name == "Valencia"
    assert config.area_at(10.49, -66.85).name == "Caracas"
    assert config.area_at(40.4, -3.7) is None


async def test_legacy_single_service_area_is_migrated(client):
    legacy = {"min_lat": 10.4, "max_lat": 10.5, "min_lng": -67.0, "max_lng": -66.8}
    async with SessionLocal() as session:
        session.add(AppSetting(key="service_area", value=legacy))
        await session.commit()
    body = (await client.get("/api/v1/config/public")).json()
    assert body["service_areas"] == [{"name": "Caracas", **legacy}]
