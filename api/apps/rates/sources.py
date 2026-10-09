"""Fetchers for the public rate sources. Each returns (rate, as_of) or raises ``RateFetchError``.

- BCV: the official average as republished by ve.dolarapi.com (the BCV site itself is often
  unreachable and has a broken certificate chain). Response: ``{"promedio": 875.65,
  "fechaActualizacion": "2026-10-09T00:00:00-04:00", ...}``.
- Binance: the public P2P ad search; the rate is the median price of the first ads offering
  USDT for VES (what a person pays to buy 1 USDT).
"""

import logging
import statistics
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

from apps.rates.models import RateSource
from kuulis.settings import settings

logger = logging.getLogger(__name__)

BINANCE_SAMPLE = 10
# Ads below this size are usually bait prices; ask for ads that sell at least this many Bs.
BINANCE_MIN_VES = 5000


class RateFetchError(Exception):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.RATES_TIMEOUT_SECONDS),
        headers={"User-Agent": f"{settings.APP_NAME}/1.0 (+{settings.PUBLIC_URL})"},
    )


def _decimal(value: object) -> Decimal:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RateFetchError(f"not a number: {value!r}") from exc
    if not rate.is_finite() or rate <= 0:
        raise RateFetchError(f"invalid rate: {value!r}")
    return rate


def _date(value: object) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


async def fetch_bcv() -> tuple[Decimal, datetime]:
    async with _client() as client:
        try:
            response = await client.get(settings.RATES_BCV_URL)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RateFetchError(f"BCV source failed: {exc}") from exc
    if not isinstance(body, dict) or "promedio" not in body:
        raise RateFetchError("BCV source: unexpected response")
    return _decimal(body["promedio"]), _date(body.get("fechaActualizacion"))


async def fetch_binance() -> tuple[Decimal, datetime]:
    payload = {
        "asset": "USDT",
        "fiat": "VES",
        "tradeType": "BUY",
        "page": 1,
        "rows": BINANCE_SAMPLE,
        "payTypes": [],
        "publisherType": None,
        "transAmount": str(BINANCE_MIN_VES),
    }
    async with _client() as client:
        try:
            response = await client.post(settings.RATES_BINANCE_URL, json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RateFetchError(f"Binance source failed: {exc}") from exc
    try:
        prices = [_decimal(item["adv"]["price"]) for item in body["data"]]
    except (KeyError, TypeError) as exc:
        raise RateFetchError("Binance source: unexpected response") from exc
    if len(prices) < 3:
        raise RateFetchError(f"Binance source: only {len(prices)} ads")
    return statistics.median(prices), datetime.now(UTC)


FETCHERS = {RateSource.BCV: fetch_bcv, RateSource.BINANCE: fetch_binance}
