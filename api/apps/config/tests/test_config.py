from apps.config import services
from apps.config.models import AppSetting
from apps.config.schemas import AppConfig, AppConfigUpdate
from conftest import set_config
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
        {
            "name": "Caracas",
            "min_lat": 10.35,
            "max_lat": 10.56,
            "min_lng": -67.1,
            "max_lng": -66.7,
            "polygon": None,
        }
    ],
    "offer_timeout_seconds": 15,
    "search_radius_m": [2000, 4000, 7000],
    "search_timeout_seconds": 180,
    "quote_ttl_seconds": 300,
    "rates_stale_minutes": {"bcv": 2160, "binance": 120},
    "rates_manual_hold_hours": 6,
    "promo_pair_alert_threshold": 3,
    "promo_pair_alert_days": 30,
    "public_activity_enabled": True,
    "public_activity_min_trips_per_hour": 3,
    "topup_min_amount": "5.00",
    "topup_binance_pay_id": "",
    "topup_account_name": "Kuulis",
    "transfer_monthly_limit": "50.00",
    "subscription_free_months": 3,
    "subscription_grace_days": 7,
    "approval_adjust_limit": "20.00",
    "approval_fares": True,
    "approval_broadcasts": True,
    "approval_waivers": True,
    "maintenance": {
        "enabled": False,
        "message": {"es": "", "en": ""},
        "eta": None,
        "areas": [],
    },
    "area_pauses": [],
    "app_links": {
        "support_whatsapp": "",
        "support_email": "",
        "emergency_number": "911",
        "terms_url": "",
        "privacy_url": "",
    },
    "location_intervals": {"online_seconds": 10, "on_ride_seconds": 4},
    "safety": {
        "pin_areas": ["Caracas"],
        "passenger_photo": "night",
        "night_start": "19:00",
        "night_end": "06:00",
        "stop_minutes": 10,
        "deviation_m": 600,
        "deviation_minutes": 3,
        "overtime_factor": 2.0,
        "check_in_seconds": 120,
        "sos_location_seconds": 5,
        "sos_team_alert": False,
    },
    "verification": {
        "expiring_documents": ["drivers_license", "medical_certificate", "vehicle_registration"],
        "optional_documents": ["criminal_record"],
        "expiry_notice_days": [30, 7, 1],
        "selfie_every_days": 7,
        "mismatch_reports": 2,
        "report_window_days": 30,
        "induction_required": False,
    },
    "support": {
        "sla_urgent_minutes": 15,
        "sla_normal_hours": 24,
        "response_promise_es": "Respondemos en menos de 24 horas.",
        "response_promise_en": "We answer within 24 hours.",
        "auto_close_days": 7,
        "auto_assign": False,
        "lost_item_days": 7,
        "lost_item_chat_hours": 72,
    },
    "notifications": {
        "quiet_start": "21:00",
        "quiet_end": "08:00",
        "marketing_daily_cap": 1,
        "inbox_retention_days": 90,
        "device_idle_days": 60,
        "monthly_summary": True,
    },
    "quality": {
        "pickup_wait_minutes": 5,
        "passenger_cancel_grace_s": 120,
        "window_days": 30,
        "driver_cancel_burst": 3,
        "driver_decline_streak": 5,
        "driver_pause_minutes": 15,
        "driver_cancel_warn": 0.15,
        "driver_cancel_low_priority": 0.25,
        "driver_cancel_review": 0.35,
        "min_rides": 10,
        "passenger_no_show_warn": 2,
        "passenger_no_show_pause": 3,
        "passenger_pause_hours": 24,
        "rating_review_below": 4.3,
        "rating_min_count": 20,
        "dispatch_quality_weight": 0.2,
    },
    "risk": {
        "window_days": 90,
        "freeze_score": 60,
        "ride_hold_score": 30,
        "max_accounts_per_device": 2,
        "min_path_share": 0.3,
        "min_duration_share": 0.3,
        "same_place_m": 150,
        "min_ride_m": 1000,
        "pair_rides": 5,
        "pair_days": 30,
        "jump_alerts": 3,
        "first_transfer_hold_hours": 24,
        "chain_minutes": 60,
        "fan_in_senders": 5,
        "new_account_days": 7,
        "rating_ring_rides": 3,
    },
    "intercity_pairs": [],
    "demand": {
        "enabled": True,
        "window_minutes": 15,
        "hot_requests": 3,
        "notify": True,
        "notify_radius_m": 3000,
        "notify_every_minutes": 30,
    },
    "referral_program": {
        "enabled": True,
        "reward_usd": "5.00",
        "required_trips": 20,
        "window_days": 30,
        "referred_free_month": False,
        "monthly_cap": 10,
        "budget_usd": "500.00",
        "starts_at": None,
        "ends_at": None,
    },
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
    await set_config(approval_fares=False)
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
    "polygon": None,
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
    assert body["service_areas"] == [{"name": "Caracas", **legacy, "polygon": None}]


async def test_public_site_for_the_website(client):
    response = await client.get("/api/v1/public/site")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "public, max-age=300"
    site = response.json()
    assert site["cities"] == ["Caracas"]
    assert site["driver"]["min_age"] == 21
    assert site["driver"]["vehicle_types"] == ["moto"]
    assert site["driver"]["vehicle_min_year"] == {"moto": 2013}  # cars are not enabled
    assert site["free_months"] == 3
    assert site["fee_tiers"][0] == {"above": "0.00", "fee": "0.00"}
    assert "topup_binance_pay_id" not in site


async def test_process_copy_skips_redis_until_invalidated() -> None:
    from kuulis.core.cache import cache_delete

    async with SessionLocal() as session:
        first = await services.get_app_config(session)
        # Gone from Redis but still served from this process's copy.
        await cache_delete(services.CACHE_KEY)
        assert await services.get_app_config(session) is first
        assert await cache_get(services.CACHE_KEY) is None

        await services.update_app_config(session, AppConfigUpdate(driver_min_age=25))
        await session.commit()
        await services.invalidate_cache()
        assert (await services.get_app_config(session)).driver_min_age == 25


async def test_invalidation_reaches_the_realtime_listener() -> None:
    import asyncio

    from apps.realtime.manager import manager
    from kuulis.core.cache import INVALIDATE_CHANNEL, local_get, local_set
    from kuulis.core.redis import redis_client

    manager.start()
    try:
        await asyncio.sleep(0.1)  # subscribed
        local_set("probe", {"x": 1})
        await redis_client.publish(INVALIDATE_CHANNEL, "probe")
        for _ in range(50):
            if local_get("probe") is None:
                break
            await asyncio.sleep(0.02)
        assert local_get("probe") is None
    finally:
        await manager.stop()
