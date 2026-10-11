import time

import pytest

from apps.monitoring import alerts, checks, stats, tasks
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings


@pytest.fixture
def sent(monkeypatch) -> list[str]:
    messages: list[str] = []

    async def fake_notify(text: str) -> None:
        messages.append(text)

    monkeypatch.setattr(alerts, "notify", fake_notify)
    return messages


@pytest.fixture(autouse=True)
def _fresh_beats(monkeypatch):
    monkeypatch.setattr(stats, "_last_beat", {})
    monkeypatch.setattr(checks, "disk_used_percent", lambda: 40.0)  # the runner's disk is not ours


async def _beat_all() -> None:
    for name in checks.expected_loops():
        await stats.beat(name)


async def test_system_health_for_staff(client, staff_headers, user_headers):
    assert (
        await client.get("/api/v1/admin/system/health", headers=user_headers)
    ).status_code == 403
    await stats.beat("dispatch")
    response = await client.get("/api/v1/admin/system/health", headers=staff_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    services = {s["name"]: s["status"] for s in body["services"]}
    assert services == {"database": "ok", "redis": "ok", "osrm": "off", "photon": "off"}
    loops = {lp["name"]: lp["status"] for lp in body["loops"]}
    assert loops["dispatch"] == "ok" and loops["subscriptions"] == "down"
    assert body["queues"]["dispatch_due"] == 0
    assert body["env"] == "test" and body["alerts"] == []


async def test_requests_are_counted(client, user_headers):
    before = (await stats.http_totals(5))["requests"]
    await client.get("/api/v1/users/me", headers=user_headers)
    await client.get("/api/health/live")  # health checks are not traffic
    assert (await stats.http_totals(5))["requests"] == before + 1


async def test_stopped_worker_is_one_alert():
    async with SessionLocal() as session:
        health = await checks.collect(session)
    keys = [p.key for p in checks.problems(health)]
    assert keys == ["worker"]

    await _beat_all()
    await redis_client.hset(stats.HEARTBEATS_KEY, "subscriptions", time.time() - 3600)
    async with SessionLocal() as session:
        health = await checks.collect(session)
    assert [p.key for p in checks.problems(health)] == ["loop:subscriptions"]


async def test_alerts_are_deduplicated_and_recover(sent, monkeypatch):
    problem = checks.Problem("service:osrm", "OSRM (rutas) no responde")
    await alerts.process([problem])
    await alerts.process([problem])  # still open, no repeat before 30 min
    assert len(sent) == 1 and "OSRM" in sent[0] and sent[0].startswith("🔴")
    assert [a.key for a in await alerts.open_alerts()] == ["service:osrm"]

    later = time.time() + alerts.REPEAT_SECONDS + 1
    monkeypatch.setattr(alerts.time, "time", lambda: later)
    await alerts.process([problem])
    assert len(sent) == 2 and "Sigue" in sent[1]

    await alerts.process([])
    assert len(sent) == 3 and sent[2].startswith("✅") and "Resuelto" in sent[2]
    assert await alerts.open_alerts() == []
    kinds = [e["kind"] for e in await alerts.history(0)]
    assert kinds == ["recovered", "alert"]


async def test_one_process_checks_per_minute(sent):
    await _beat_all()
    assert await tasks.run_once() is True
    assert await tasks.run_once() is False
    assert sent == []  # healthy system, nothing to say


async def test_overview_counts_open_alerts(client, staff_headers, sent):
    await alerts.process([checks.Problem("disk", "Disco al 90 %")])
    body = (await client.get("/api/v1/admin/overview", headers=staff_headers)).json()
    assert body["open_alerts"] == 1


async def test_metrics_need_the_token(client, monkeypatch):
    assert (await client.get("/api/metrics")).status_code == 404
    monkeypatch.setattr(settings, "METRICS_TOKEN", "s3cret")
    assert (
        await client.get("/api/metrics", headers={"Authorization": "Bearer wrong"})
    ).status_code == 404
    response = await client.get("/api/metrics", headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 200
    assert 'kuulis_service_up{env="test",service="database"} 1' in response.text
    assert "kuulis_drivers_online" in response.text


def test_log_lines_carry_request_ids():
    import json
    import logging

    from kuulis.core.logging import JSONFormatter
    from kuulis.core.request_context import log_fields_ctx, request_id_ctx, set_log_field

    tokens = request_id_ctx.set("req-1"), log_fields_ctx.set({"ride_id": "r-1"})
    try:
        set_log_field("user_id", "u-1")
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
        line = json.loads(JSONFormatter().format(record))
    finally:
        request_id_ctx.reset(tokens[0])
        log_fields_ctx.reset(tokens[1])
    assert (line["request_id"], line["ride_id"], line["user_id"]) == ("req-1", "r-1", "u-1")
