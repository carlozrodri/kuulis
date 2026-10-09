from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from apps.rates import services, sources
from apps.rates.models import ExchangeRate, RateOrigin, RateSource
from apps.rates.schemas import FrozenRates
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client

API = "/api/v1"


async def _auto(source: RateSource, rate: str, age: timedelta = timedelta(0)) -> None:
    async with SessionLocal() as session:
        if age:
            now = datetime.now(UTC) - age
            session.add(
                ExchangeRate(
                    source=source,
                    rate=Decimal(rate),
                    origin=RateOrigin.AUTO,
                    as_of=now,
                    fetched_at=now,
                )
            )
            await session.commit()
            await redis_client.delete(services._current_key(source))
        else:
            assert await services.record_auto(session, source, Decimal(rate), datetime.now(UTC))


async def test_rates_empty_then_current(client):
    assert (await client.get(f"{API}/rates")).json() == {"bcv": None, "binance": None}
    await _auto(RateSource.BCV, "875.6505")
    await _auto(RateSource.BINANCE, "1004")
    body = (await client.get(f"{API}/rates")).json()
    assert body["bcv"]["rate"] == "875.65"
    assert body["bcv"]["origin"] == "auto" and body["bcv"]["stale"] is False
    assert body["binance"]["rate"] == "1004.00"


async def test_stale_rate_from_database(client):
    await _auto(RateSource.BINANCE, "990", age=timedelta(hours=3))  # default stale after 2 h
    body = (await client.get(f"{API}/rates")).json()
    assert body["binance"]["rate"] == "990.00" and body["binance"]["stale"] is True


async def test_jump_guard():
    await _auto(RateSource.BCV, "800")
    async with SessionLocal() as session:
        assert not await services.record_auto(
            session, RateSource.BCV, Decimal("2000"), datetime.now(UTC)
        )
        assert await services.record_auto(
            session, RateSource.BCV, Decimal("820"), datetime.now(UTC)
        )


async def test_manual_rate_holds_and_history(client, admin_headers, staff_headers):
    await _auto(RateSource.BCV, "800")
    payload = {"source": "bcv", "rate": "812.5", "note": "BCV caído"}
    forbidden = await client.post(f"{API}/admin/rates", json=payload, headers=staff_headers)
    assert forbidden.status_code == 403
    response = await client.post(f"{API}/admin/rates", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    assert response.json()["origin"] == "manual" and response.json()["rate"] == "812.50"
    assert (await client.get(f"{API}/rates")).json()["bcv"]["rate"] == "812.50"

    async with SessionLocal() as session:  # automatic results wait while the manual one holds
        assert not await services.record_auto(
            session, RateSource.BCV, Decimal("805"), datetime.now(UTC)
        )
    assert (await client.get(f"{API}/rates")).json()["bcv"]["origin"] == "manual"

    history = await client.get(f"{API}/admin/rates/history?source=bcv", headers=staff_headers)
    assert history.status_code == 200
    items = history.json()["items"]
    assert [i["rate"] for i in items] == ["812.50", "800.00"]
    assert items[0]["created_by"]["name"] and items[0]["note"] == "BCV caído"
    assert items[1]["created_by"] is None

    bad = await client.post(
        f"{API}/admin/rates", json={"source": "bcv", "rate": "-1"}, headers=admin_headers
    )
    assert bad.status_code == 422


async def test_refresh_uses_fetchers(client, admin_headers, monkeypatch):
    async def ok():
        return Decimal("1001.5"), datetime.now(UTC)

    async def broken():
        raise sources.RateFetchError("down")

    monkeypatch.setitem(sources.FETCHERS, RateSource.BINANCE, ok)
    monkeypatch.setitem(sources.FETCHERS, RateSource.BCV, broken)
    response = await client.post(f"{API}/admin/rates/refresh", json={}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["binance"]["rate"] == "1001.50"
    assert response.json()["bcv"] is None


async def test_poll_due_runs_once_per_interval(monkeypatch):
    calls = []

    async def fetch(session, source):
        calls.append(source)
        return True

    monkeypatch.setattr(services, "fetch", fetch)
    async with SessionLocal() as session:
        await services.poll_due(session)
        await services.poll_due(session)
    assert sorted(calls) == [RateSource.BCV, RateSource.BINANCE]


def test_to_ves():
    rates = FrozenRates(bcv=Decimal("875.6505"), binance=None)
    ves = services.to_ves(Decimal("2.40"), rates)
    assert ves.bcv == Decimal("2101.56") and ves.binance is None


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"promedio": 875.6505, "fechaActualizacion": "2026-10-09T00:00:00-04:00"}, "875.6505"),
    ],
)
async def test_fetch_bcv_parses(monkeypatch, body, expected):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    monkeypatch.setattr(
        sources, "_client", lambda: httpx.AsyncClient(transport=transport, base_url="http://x")
    )
    rate, as_of = await sources.fetch_bcv()
    assert rate == Decimal(expected) and as_of.tzinfo is not None


async def test_fetch_binance_median(monkeypatch):
    prices = ["1010.5", "1011.6", "1012", "1012", "1013.5"]
    body = {"data": [{"adv": {"price": p}} for p in prices]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    monkeypatch.setattr(
        sources, "_client", lambda: httpx.AsyncClient(transport=transport, base_url="http://x")
    )
    rate, _ = await sources.fetch_binance()
    assert rate == Decimal("1012")

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": []}))
    monkeypatch.setattr(
        sources, "_client", lambda: httpx.AsyncClient(transport=transport, base_url="http://x")
    )
    with pytest.raises(sources.RateFetchError):
        await sources.fetch_binance()
