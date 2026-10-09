"""Binance Pay reconciliation: reads the Pay history of Kuulis' Binance account and records every
incoming USDT payment (``services.record_payment`` credits the driver whose Binance Pay ID paid).

Needs a read-only API key (``BINANCE_API_KEY`` / ``BINANCE_API_SECRET``). The endpoint is
``GET /sapi/v1/pay/transactions`` (signed): each item has ``transactionId``, ``transactionTime``
(ms), ``amount`` (negative for outgoing), ``currency`` and ``payerInfo: {name, binanceId}``.
"""

import hashlib
import hmac
import logging
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.wallet import services
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

CURSOR_KEY = f"{settings.APP_ENV}:wallet:binance:cursor"
LOCK_KEY = f"{settings.APP_ENV}:wallet:binance:lock"
OVERLAP_MS = 10 * 60 * 1000  # re-read the last minutes: late entries; duplicates are ignored
FIRST_LOOKBACK_MS = 24 * 3600 * 1000
POLL_SECONDS = 60


def enabled() -> bool:
    return bool(settings.BINANCE_API_KEY and settings.BINANCE_API_SECRET)


def _signed(params: dict) -> str:
    query = urlencode(params)
    signature = hmac.new(
        settings.BINANCE_API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    return f"{query}&signature={signature}"


async def fetch_transactions(start_ms: int, end_ms: int) -> list[dict]:
    params = {
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 100,
        "recvWindow": 10000,
        "timestamp": int(time.time() * 1000),
    }
    url = f"{settings.BINANCE_API_URL.rstrip('/')}/sapi/v1/pay/transactions?{_signed(params)}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, headers={"X-MBX-APIKEY": settings.BINANCE_API_KEY})
        response.raise_for_status()
        body = response.json()
    return list(body.get("data") or [])


def parse(item: dict) -> tuple[str, Decimal, str | None, str | None] | None:
    """(transaction id, amount, payer Binance Pay ID, payer name) for incoming USDT, else None."""
    if str(item.get("currency", "")).upper() != "USDT":
        return None
    try:
        amount = Decimal(str(item.get("amount")))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    payer = item.get("payerInfo") or {}
    payer_id = payer.get("binanceId")
    return (
        str(item["transactionId"]),
        amount.quantize(Decimal("0.01")),
        str(payer_id) if payer_id not in (None, "") else None,
        payer.get("name"),
    )


async def reconcile(session: AsyncSession) -> int:
    """One pass. Returns how many new payments were recorded."""
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=POLL_SECONDS - 5):
        return 0
    now_ms = int(time.time() * 1000)
    cursor = await redis_client.get(CURSOR_KEY)
    start = int(cursor) - OVERLAP_MS if cursor else now_ms - FIRST_LOOKBACK_MS
    items = await fetch_transactions(start, now_ms)
    recorded = 0
    for item in sorted(items, key=lambda i: i.get("transactionTime", 0)):
        parsed = parse(item)
        if parsed is None:
            continue
        transaction_id, amount, payer_id, payer_name = parsed
        top_up = await services.record_payment(
            session, transaction_id, amount, payer_id, payer_name
        )
        await session.commit()
        if top_up is not None:
            recorded += 1
            logger.info("Binance Pay %s: %s USDT (%s)", transaction_id, amount, top_up.status)
    await redis_client.set(CURSOR_KEY, str(now_ms))
    return recorded
