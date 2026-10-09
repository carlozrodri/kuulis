"""Expo push service client (delivers to both APNs and FCM through Expo)."""

import logging
from typing import Any

import httpx

from kuulis.settings import settings

logger = logging.getLogger(__name__)
EXPO_BATCH_SIZE = 100


async def send_expo_push(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Returns Expo tickets in the same order as the messages."""
    if not settings.PUSH_ENABLED or not messages:
        return []
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.EXPO_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {settings.EXPO_ACCESS_TOKEN}"
    tickets: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for start in range(0, len(messages), EXPO_BATCH_SIZE):
            chunk = messages[start : start + EXPO_BATCH_SIZE]
            response = await client.post(settings.EXPO_PUSH_URL, json=chunk, headers=headers)
            response.raise_for_status()
            tickets.extend(response.json().get("data", []))
    return tickets
