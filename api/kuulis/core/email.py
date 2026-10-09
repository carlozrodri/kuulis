"""Transactional email through Resend. Always sent from a background task."""

import logging

import httpx

from kuulis.settings import settings

logger = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    if not settings.EMAIL_ENABLED or not settings.RESEND_API_KEY:
        logger.info("Email disabled, skipping '%s' to %s", subject, to)
        return False
    payload = {"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html}
    if text:
        payload["text"] = text
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
    if response.status_code >= 400:
        logger.error("Resend error %s: %s", response.status_code, response.text[:500])
        response.raise_for_status()
    return True
