"""Shareable ride receipt (doc 23): an image with the route, the price in USD and in bolívares at
the rates frozen on the ride, and the payment method agreed with the driver.

The image lives behind a signed link (``/public/rides/receipts/{token}.png``) so it can be sent
by WhatsApp to a company that reimburses the ride. The token is the ride id plus an HMAC of it
and the language, so nobody can guess another ride's receipt. Kuulis does not charge the ride, so
the receipt says it is not a fiscal invoice.
"""

import base64
import hashlib
import hmac
import io
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from apps.rates.services import to_ves
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.schemas import RideReceipt
from apps.users.models import User
from kuulis.core.calendar import CARACAS_TZ
from kuulis.core.exceptions import ConflictError, NotFoundError
from kuulis.settings import settings

ASSETS = Path(__file__).parent / "assets"
LANGS = ("es", "en")
WIDTH = 1080
PAD = 72

# Brand colours (mobile/src/theme, light).
PRIMARY = (14, 124, 90)
ACCENT = (255, 200, 61)
TEXT = (20, 32, 27)
MUTED = (91, 106, 99)
BORDER = (220, 230, 224)
SURFACE = (243, 247, 245)
WHITE = (255, 255, 255)


class ReceiptUnavailableError(ConflictError):
    code = "receipt_unavailable"
    message = "Only completed rides have a receipt"


class ReceiptNotFoundError(NotFoundError):
    code = "receipt_not_found"
    message = "Receipt not found"


# --- Signed link -------------------------------------------------------------------------------


def _signature(ride_id: uuid.UUID, lang: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(), f"ride-receipt:{ride_id}:{lang}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest[:16]).decode().rstrip("=")


def token_for(ride_id: uuid.UUID, lang: str) -> str:
    lang = lang if lang in LANGS else "es"
    return f"{ride_id.hex}{lang}{_signature(ride_id, lang)}"


def parse_token(token: str) -> tuple[uuid.UUID, str]:
    """``(ride_id, lang)``; ReceiptNotFoundError when the token is malformed or forged."""
    try:
        ride_id = uuid.UUID(hex=token[:32])
    except ValueError:
        raise ReceiptNotFoundError() from None
    lang = token[32:34]
    if lang not in LANGS or not hmac.compare_digest(token[34:], _signature(ride_id, lang)):
        raise ReceiptNotFoundError()
    return ride_id, lang


def image_url(ride_id: uuid.UUID, lang: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}{settings.API_V1_PREFIX}/public/rides/receipts/{token_for(ride_id, lang)}.png"


# --- Data --------------------------------------------------------------------------------------


@dataclass
class _People:
    passenger: str
    driver: str


def _first(name: str | None) -> str:
    parts = (name or "").split()
    return parts[0] if parts else ""


def number(ride: Ride) -> str:
    """Short code people can quote to support: the start of the ride id."""
    return ride.id.hex[:8].upper()


async def _people(session: AsyncSession, ride: Ride) -> _People:
    passenger = await session.get(User, ride.passenger_id)
    driver = await session.get(User, ride.driver_id) if ride.driver_id else None
    return _People(
        passenger=_first(ride.rider_name) or _first(passenger.full_name if passenger else None),
        driver=_first(driver.full_name if driver else None),
    )


def _rates(ride: Ride):
    from apps.rides.events import _frozen

    return _frozen(ride)


async def build(session: AsyncSession, ride: Ride, lang: str) -> RideReceipt:
    if ride.status != RideStatus.COMPLETED:
        raise ReceiptUnavailableError(details={"status": ride.status.value})
    people = await _people(session, ride)
    frozen = _rates(ride)
    lang = lang if lang in LANGS else "es"
    return RideReceipt(
        ride_id=ride.id,
        number=number(ride),
        completed_at=ride.completed_at or ride.requested_at,
        pickup_address=ride.pickup_address,
        dropoff_address=ride.dropoff_address,
        distance_m=ride.distance_m,
        duration_s=ride.duration_s,
        fare=ride.fare,
        discount=ride.discount,
        total=ride.total,
        rates=frozen,
        total_ves=to_ves(ride.total, frozen),
        payment_method=ride.payment_method,
        passenger_name=people.passenger,
        driver_name=people.driver,
        plate=(ride.vehicle or {}).get("plate") or None,
        image_url=image_url(ride.id, lang),
    )


# --- Image -------------------------------------------------------------------------------------

_TEXTS = {
    "es": {
        "title": "Recibo de viaje",
        "number": "N.º",
        "from": "Origen",
        "to": "Destino",
        "distance": "Distancia",
        "duration": "Duración",
        "fare": "Tarifa",
        "discount": "Descuento Kuulis",
        "total": "Total",
        "ves": "Equivalente en bolívares",
        "rate": "Tasa {source}: Bs {rate} por USD",
        "payment": "Método de pago acordado",
        "passenger": "Pasajero",
        "driver": "Motorizado",
        "plate": "Placa",
        "footer": "Pagado directamente al motorizado. Kuulis no cobra el viaje: "
        "este recibo no es una factura fiscal.",
        "no_rate": "Tasa no disponible",
    },
    "en": {
        "title": "Ride receipt",
        "number": "No.",
        "from": "Pickup",
        "to": "Destination",
        "distance": "Distance",
        "duration": "Duration",
        "fare": "Fare",
        "discount": "Kuulis discount",
        "total": "Total",
        "ves": "In bolívares",
        "rate": "{source} rate: Bs {rate} per USD",
        "payment": "Payment method agreed",
        "passenger": "Passenger",
        "driver": "Driver",
        "plate": "Plate",
        "footer": "Paid directly to the driver. Kuulis does not charge the ride: "
        "this receipt is not a tax invoice.",
        "no_rate": "Rate not available",
    },
}

_PAYMENT = {
    "es": {
        PaymentMethod.CASH_USD: "Efectivo en dólares",
        PaymentMethod.CASH_VES: "Efectivo en bolívares",
        PaymentMethod.PAGO_MOVIL: "Pago móvil",
        PaymentMethod.BINANCE: "Binance",
        PaymentMethod.ZELLE: "Zelle",
    },
    "en": {
        PaymentMethod.CASH_USD: "Cash (USD)",
        PaymentMethod.CASH_VES: "Cash (bolívares)",
        PaymentMethod.PAGO_MOVIL: "Pago móvil",
        PaymentMethod.BINANCE: "Binance",
        PaymentMethod.ZELLE: "Zelle",
    },
}


@cache
def _logo() -> Image.Image:
    """The «K punto» logo, negative version (white on the green band), 64 px high."""
    return Image.open(ASSETS / "kuulis-horizontal-negativo.png").convert("RGBA")


@cache
def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / f"PlusJakartaSans_{weight}.ttf"), size)


def _money(value: Decimal, lang: str) -> str:
    text = f"{value:,.2f}"
    return text if lang == "en" else text.replace(",", "_").replace(".", ",").replace("_", ".")


def _distance(meters: int, lang: str) -> str:
    km = meters / 1000
    text = f"{km:.1f} km"
    return text if lang == "en" else text.replace(".", ",")


def _duration(seconds: int) -> str:
    minutes = max(round(seconds / 60), 1)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h {minutes % 60:02d} min"


def _date(value: datetime, lang: str) -> str:
    local = value.astimezone(CARACAS_TZ)
    if lang == "en":
        return local.strftime("%b %d, %Y · %I:%M %p").replace(" 0", " ")
    months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{local.day} {months[local.month - 1]} {local.year} · {local:%H:%M}"


class _Canvas:
    """Draws top to bottom on a tall white page; ``finish`` crops it to the content."""

    def __init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH, 2600), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.y = 0

    def text(self, value: str, font, fill=TEXT, x: int = PAD, gap: int = 12) -> None:
        self.draw.text((x, self.y), value, font=font, fill=fill)
        self.y += font.size + gap

    def wrapped(self, value: str, font, fill=TEXT, x: int = PAD, width: int = 44) -> None:
        for line in textwrap.wrap(value or "—", width=width)[:3]:
            self.text(line, font, fill, x=x, gap=8)

    def row(self, label: str, value: str, font=None, fill=TEXT) -> None:
        """Label on the left, value on the right, both on the same baseline."""
        font = font or _font("400Regular", 34)
        height = max(font.size, 34)
        self.draw.text((PAD, self.y + height - 34), label, font=_font("400Regular", 34), fill=MUTED)
        right = WIDTH - PAD - self.draw.textlength(value, font=font)
        self.draw.text((right, self.y + height - font.size), value, font=font, fill=fill)
        self.y += height + 22

    def rule(self) -> None:
        self.y += 10
        self.draw.line((PAD, self.y, WIDTH - PAD, self.y), fill=BORDER, width=2)
        self.y += 32

    def finish(self) -> bytes:
        out = io.BytesIO()
        self.image.crop((0, 0, WIDTH, self.y + PAD)).save(out, format="PNG", optimize=True)
        return out.getvalue()


def render(receipt: RideReceipt, lang: str) -> bytes:
    t = _TEXTS[lang]
    c = _Canvas()

    # Header band: brand and receipt title.
    c.draw.rectangle((0, 0, WIDTH, 260), fill=PRIMARY)
    logo = _logo()
    c.image.paste(logo, (PAD, 72), logo)
    c.draw.text((PAD, 168), t["title"], font=_font("700Bold", 40), fill=WHITE)
    c.y = 316

    c.text(_date(receipt.completed_at, lang), _font("700Bold", 36))
    c.text(f"{t['number']} {receipt.number}", _font("400Regular", 30), fill=MUTED, gap=24)
    c.rule()

    # Route: a dot for each end, as in the app.
    for key, address, colour in (
        ("from", receipt.pickup_address, PRIMARY),
        ("to", receipt.dropoff_address, ACCENT),
    ):
        c.draw.ellipse((PAD, c.y + 8, PAD + 24, c.y + 32), fill=colour)
        c.text(t[key], _font("400Regular", 30), fill=MUTED, x=PAD + 48, gap=6)
        c.wrapped(address, _font("700Bold", 34), x=PAD + 48)
        c.y += 18
    c.row(t["distance"], _distance(receipt.distance_m, lang))
    c.row(t["duration"], _duration(receipt.duration_s))
    c.rule()

    if receipt.discount > 0:
        c.row(t["fare"], f"$ {_money(receipt.fare, lang)}")
        c.row(t["discount"], f"- $ {_money(receipt.discount, lang)}")
        c.y += 8
    c.row(t["total"], f"$ {_money(receipt.total, lang)}", font=_font("800ExtraBold", 64))
    c.y += 12

    # Bolívares at the rates frozen when the ride was requested.
    c.draw.rounded_rectangle((PAD, c.y, WIDTH - PAD, c.y + 216), radius=28, fill=SURFACE)
    c.y += 28
    c.text(t["ves"], _font("400Regular", 30), fill=MUTED, x=PAD + 32, gap=14)
    for source, amount, rate in (
        ("BCV", receipt.total_ves.bcv, receipt.rates.bcv),
        ("Binance", receipt.total_ves.binance, receipt.rates.binance),
    ):
        if amount is None or rate is None:
            line = f"{source}: {t['no_rate']}"
            c.text(line, _font("400Regular", 30), fill=MUTED, x=PAD + 32, gap=14)
            continue
        value = f"Bs {_money(amount, lang)}"
        c.draw.text((PAD + 32, c.y), value, font=_font("700Bold", 34), fill=TEXT)
        note = t["rate"].format(source=source, rate=_money(rate, lang))
        width = c.draw.textlength(note, font=_font("400Regular", 26))
        c.draw.text(
            (WIDTH - PAD - 32 - width, c.y + 6), note, font=_font("400Regular", 26), fill=MUTED
        )
        c.y += 34 + 20
    c.y += 40

    c.row(t["payment"], _PAYMENT[lang].get(receipt.payment_method, receipt.payment_method))
    if receipt.passenger_name:
        c.row(t["passenger"], receipt.passenger_name)
    if receipt.driver_name:
        c.row(t["driver"], receipt.driver_name)
    if receipt.plate:
        c.row(t["plate"], receipt.plate)
    c.rule()
    c.wrapped(t["footer"], _font("400Regular", 28), fill=MUTED, width=60)
    return c.finish()
