"""Branded emails (doc 14): one layout and the texts of every email, in Spanish and English.

The layout is a single-column table with inline styles, the form Gmail (web and Android) and
Outlook render the same. Values are user input: they are escaped before they reach the HTML.
"""

import html
import uuid
from dataclasses import dataclass, field
from typing import Any

from kuulis.settings import settings

BRAND = "#0E7C5A"
INK = "#14201B"
MUTED = "#5B6B64"
LINE = "#E4EAE7"
PAPER = "#F4F7F5"


@dataclass(frozen=True)
class Text:
    subject: str
    heading: str
    paragraphs: tuple[str, ...]
    cta: str | None = None  # button label; the link is the ``link`` value
    closing: tuple[str, ...] = ()  # paragraphs after the quote and the button


@dataclass(frozen=True)
class Template:
    label: str
    description: str
    es: Text
    en: Text
    sample: dict[str, str] = field(default_factory=dict)
    sample_en: dict[str, str] = field(default_factory=dict)  # English values over ``sample``
    # A value shown as a quoted block under the paragraphs (a support answer).
    quote: str | None = None


# Closing line of the emails that are also a receipt (doc 17). Without a company, not fiscal.
RECEIPT_ES = (
    "Recibo no fiscal N.º {receipt} · saldo después: {balance} USDT. "
    "También lo ves en la app, en Billetera."
)
RECEIPT_EN = (
    "Non-fiscal receipt No. {receipt} · balance after: {balance} USDT. "
    "You can also see it in the app, under Wallet."
)

TEMPLATES: dict[str, Template] = {
    "verify": Template(
        "Confirmar correo",
        "Al crear la cuenta o pedir otro enlace.",
        Text(
            "Confirma tu correo",
            "Confirma tu correo",
            ("Hola {name}, toca el botón para confirmar tu correo y terminar tu registro.",),
            "Confirmar correo",
        ),
        Text(
            "Confirm your email",
            "Confirm your email",
            ("Hi {name}, tap the button to confirm your email and finish signing up.",),
            "Confirm email",
        ),
        {"name": "Ana", "link": "https://kuulis.app/verify-email?token=ejemplo"},
    ),
    "welcome": Template(
        "Bienvenida",
        "Cuando el usuario confirma su correo.",
        Text(
            "Bienvenido a Kuulis",
            "¡Bienvenido a Kuulis, {name}!",
            (
                "Ya puedes pedir tu moto: escribe a dónde vas y un motorizado cercano te busca.",
                "En Kuulis le pagas directo al motorizado y sin comisiones escondidas.",
            ),
            "Abrir Kuulis",
        ),
        Text(
            "Welcome to Kuulis",
            "Welcome to Kuulis, {name}!",
            (
                "You can request your moto now: type where you are going and a nearby driver "
                "picks you up.",
                "In Kuulis you pay the driver directly, with no hidden commissions.",
            ),
            "Open Kuulis",
        ),
        {"name": "Ana", "link": "https://kuulis.app"},
    ),
    "reset": Template(
        "Restablecer contraseña",
        "Cuando alguien pide cambiar la contraseña.",
        Text(
            "Restablece tu contraseña",
            "Restablece tu contraseña",
            (
                "Hola {name}, toca el botón para crear una contraseña nueva.",
                "Si no lo pediste, ignora este correo: tu contraseña no cambia.",
            ),
            "Crear contraseña nueva",
        ),
        Text(
            "Reset your password",
            "Reset your password",
            (
                "Hi {name}, tap the button to create a new password.",
                "If you did not ask for it, ignore this email: your password stays the same.",
            ),
            "Create a new password",
        ),
        {"name": "Ana", "link": "https://kuulis.app/reset-password?token=ejemplo"},
    ),
    "password_changed": Template(
        "Contraseña cambiada",
        "Después de cambiar o restablecer la contraseña.",
        Text(
            "Tu contraseña cambió",
            "Tu contraseña cambió",
            (
                "Hola {name}, la contraseña de tu cuenta de Kuulis acaba de cambiar y cerramos "
                "la sesión en tus otros teléfonos.",
                "Si no fuiste tú, restablece tu contraseña ahora y escríbenos.",
            ),
            "Restablecer contraseña",
        ),
        Text(
            "Your password changed",
            "Your password changed",
            (
                "Hi {name}, the password of your Kuulis account just changed and we signed you "
                "out on your other phones.",
                "If it was not you, reset your password now and write to us.",
            ),
            "Reset password",
        ),
        {"name": "Ana", "link": "https://kuulis.app/ayuda/no-puedo-entrar"},
    ),
    "invite": Template(
        "Invitación al equipo",
        "Al invitar a alguien al panel de administración.",
        Text(
            "Te invitaron al equipo de Kuulis",
            "Te invitaron al equipo de Kuulis",
            (
                "Hola {name}, te invitaron al panel de administración de Kuulis.",
                "Crea tu contraseña con el botón. El enlace vence en 3 días.",
            ),
            "Crear mi contraseña",
        ),
        Text(
            "You were invited to the Kuulis team",
            "You were invited to the Kuulis team",
            (
                "Hi {name}, you were invited to the Kuulis admin panel.",
                "Create your password with the button. The link expires in 3 days.",
            ),
            "Create my password",
        ),
        {"name": "Luis", "link": "https://admin.kuulis.app/accept-invite?token=ejemplo"},
    ),
    "login_locked": Template(
        "Intentos fallidos",
        "Cuando bloqueamos la cuenta unos minutos por intentos fallidos.",
        Text(
            "Intentos fallidos de entrar a tu cuenta",
            "Intentos fallidos de entrar",
            (
                "Hola {name}, hubo varios intentos fallidos de entrar a tu cuenta de Kuulis y la "
                "bloqueamos unos minutos.",
                "Si no fuiste tú, cambia tu contraseña desde la app (Olvidé mi contraseña).",
            ),
        ),
        Text(
            "Failed sign-in attempts on your account",
            "Failed sign-in attempts",
            (
                "Hi {name}, there were several failed attempts to sign in to your Kuulis account, "
                "so we locked it for a few minutes.",
                "If it was not you, change your password in the app (Forgot password).",
            ),
        ),
        {"name": "Ana"},
    ),
    "driver_approved": Template(
        "Motorizado aprobado",
        "Cuando aprobamos a un motorizado.",
        Text(
            "¡Ya puedes manejar con Kuulis!",
            "¡Bienvenido, {name}!",
            (
                "Revisamos tus documentos y tu cuenta de motorizado está aprobada.",
                "Abre la app y toca Conectarme para empezar a recibir viajes.",
            ),
            "Abrir Kuulis",
        ),
        Text(
            "You can drive with Kuulis now!",
            "Welcome, {name}!",
            (
                "We reviewed your documents and your driver account is approved.",
                "Open the app and tap Go online to start getting rides.",
            ),
            "Open Kuulis",
        ),
        {"name": "Luis", "link": "https://kuulis.app"},
    ),
    "driver_rejected": Template(
        "Motorizado rechazado",
        "Cuando no aprobamos una solicitud de motorizado.",
        Text(
            "Revisamos tu solicitud",
            "Revisamos tu solicitud",
            (
                "Hola {name}, por ahora no pudimos aprobar tu cuenta de motorizado.",
                "Motivo: {reason}",
                "Puedes corregirlo desde la app y enviarla de nuevo.",
            ),
        ),
        Text(
            "We reviewed your application",
            "We reviewed your application",
            (
                "Hi {name}, we could not approve your driver account for now.",
                "Reason: {reason}",
                "You can fix it in the app and send it again.",
            ),
        ),
        {"name": "Luis", "reason": "La foto de la licencia no se lee bien."},
        {"reason": "The photo of the license is not readable."},
    ),
    "document_expiring": Template(
        "Documento por vencer",
        "Avisos de documentos del motorizado a 30, 7 y 1 día.",
        Text(
            "Tu {document} vence pronto",
            "Tu {document} vence el {date}",
            (
                "Hola {name}, sube el documento renovado antes de esa fecha para seguir "
                "recibiendo viajes.",
                "Hazlo desde Perfil → Mis documentos → Renovar.",
            ),
        ),
        Text(
            "Your {document} expires soon",
            "Your {document} expires on {date}",
            (
                "Hi {name}, upload the renewed document before that date to keep receiving rides.",
                "Do it from Profile → My documents → Renew.",
            ),
        ),
        {"name": "Luis", "document": "licencia de conducir", "date": "30/10/2026"},
        {"document": "driver's license"},
    ),
    "top_up_credited": Template(
        "Recarga acreditada",
        "Cuando confirmamos una recarga de la billetera.",
        Text(
            "Recarga acreditada",
            "Sumamos {amount} USDT a tu billetera",
            ("Hola {name}, tu recarga ya está en tu billetera de Kuulis.",),
            closing=(RECEIPT_ES,),
        ),
        Text(
            "Top-up credited",
            "We added {amount} USDT to your wallet",
            ("Hi {name}, your top-up is in your Kuulis wallet now.",),
            closing=(RECEIPT_EN,),
        ),
        {"name": "Luis", "amount": "10.00", "receipt": "000123", "balance": "14.50"},
    ),
    "fee_paid": Template(
        "Recibo de cuota",
        "Recibo de la cuota mensual pagada.",
        Text(
            "Recibo de tu cuota de {month}",
            "Pagaste tu cuota de {month}",
            (
                "Hola {name}, descontamos {fee} USDT de tu billetera por la cuota de {month}.",
                "Kuulis no cobra comisión por viaje: solo esta cuota en los meses en que "
                "trabajas. ¡Gracias!",
            ),
            closing=(RECEIPT_ES,),
        ),
        Text(
            "Receipt for your {month} fee",
            "You paid your {month} fee",
            (
                "Hi {name}, we took {fee} USDT from your wallet for the {month} fee.",
                "Kuulis takes no commission per ride: only this fee in the months you work. "
                "Thank you!",
            ),
            closing=(RECEIPT_EN,),
        ),
        {
            "name": "Luis",
            "fee": "5.00",
            "month": "septiembre 2026",
            "receipt": "000124",
            "balance": "9.50",
        },
        {"month": "September 2026"},
    ),
    "fee_pending": Template(
        "Aviso de cuota",
        "Cuando la billetera no alcanza para la cuota del mes.",
        Text(
            "Tu cuota de {month}",
            "Te toca pagar {fee} USDT",
            (
                "Hola {name}, tu cuota de {month} es de {fee} USDT y tu billetera no alcanza.",
                "Recárgala antes del {due} para seguir recibiendo viajes.",
            ),
        ),
        Text(
            "Your {month} fee",
            "You owe {fee} USDT",
            (
                "Hi {name}, your {month} fee is {fee} USDT and your wallet does not cover it.",
                "Top it up before {due} to keep receiving rides.",
            ),
        ),
        {"name": "Luis", "fee": "5.00", "month": "septiembre 2026", "due": "5 de octubre"},
        {"month": "September 2026", "due": "October 5"},
    ),
    "monthly_summary": Template(
        "Estado de cuenta mensual",
        "El día 1, apenas se cobran las cuotas: el estado de cuenta del mes anterior.",
        Text(
            "Tu estado de cuenta de {month}",
            "Tu mes en Kuulis",
            (
                "Hola {name}, en {month} hiciste {rides} viajes y ganaste {earnings} USD "
                "según la app.",
                "Tramo: más de {tier} USD · cuota del mes: {fee} USDT.",
                "Billetera: recargas {top_ups} · créditos de promoción {promo} · "
                "transferencias recibidas {transfers_in} y enviadas {transfers_out} USDT.",
                "Saldo al cierre del mes: {balance} USDT.",
            ),
            closing=("El detalle está en la app: Billetera → Estado de cuenta.",),
        ),
        Text(
            "Your {month} statement",
            "Your month in Kuulis",
            (
                "Hi {name}, in {month} you did {rides} rides and earned {earnings} USD "
                "according to the app.",
                "Tier: above {tier} USD · fee for the month: {fee} USDT.",
                "Wallet: top-ups {top_ups} · promotion credits {promo} · transfers received "
                "{transfers_in} and sent {transfers_out} USDT.",
                "Balance at the end of the month: {balance} USDT.",
            ),
            closing=("The details are in the app: Wallet → Statement.",),
        ),
        {
            "name": "Luis",
            "month": "septiembre 2026",
            "rides": "84",
            "earnings": "312.50",
            "tier": "300.00",
            "fee": "15.00",
            "top_ups": "20.00",
            "promo": "6.40",
            "transfers_in": "0.00",
            "transfers_out": "5.00",
            "balance": "11.90",
        },
        {"month": "September 2026"},
    ),
    "campaign": Template(
        "Campaña",
        "Mensaje de una campaña por correo (texto de la campaña).",
        Text(
            "{title}",
            "{title}",
            (
                "{body}",
                "Puedes dejar de recibir estos correos en la app: Perfil → Ajustes → "
                "Notificaciones.",
            ),
            "Abrir Kuulis",
        ),
        Text(
            "{title}",
            "{title}",
            (
                "{body}",
                "You can stop these emails in the app: Profile → Settings → Notifications.",
            ),
            "Open Kuulis",
        ),
        {
            "title": "Viaja más barato este fin de semana",
            "body": "Este sábado y domingo tus viajes tienen 20 % de descuento.",
            "link": "https://kuulis.app",
        },
    ),
    "support_received": Template(
        "Soporte: recibimos tu mensaje",
        "Al escribir desde el formulario de la web.",
        Text(
            "Recibimos tu mensaje",
            "Recibimos tu mensaje",
            ("Hola, te responderemos a este correo.",),
        ),
        Text(
            "We got your message",
            "We got your message",
            ("Hi, we will answer to this email.",),
        ),
        {"text": "No puedo entrar a mi cuenta."},
        quote="text",
    ),
    "support_reply": Template(
        "Soporte: respuesta",
        "Cuando el equipo responde un ticket.",
        Text(
            "Respuesta de soporte de Kuulis",
            "Te respondemos",
            ("Hola, esta es nuestra respuesta:",),
            closing=("Si necesitas algo más, responde a este correo.",),
        ),
        Text(
            "Kuulis support answer",
            "Our answer",
            ("Hi, here is our answer:",),
            closing=("If you need anything else, reply to this email.",),
        ),
        {"text": "Ya revisamos tu viaje y te devolvimos la diferencia."},
        quote="text",
    ),
    "support_closed": Template(
        "Soporte: consulta cerrada",
        "Cuando cerramos una consulta sin respuesta del usuario.",
        Text(
            "Cerramos tu consulta",
            "Cerramos tu consulta",
            ("Hola, como no tuvimos noticias tuyas, cerramos la consulta.",),
            closing=("Si aún necesitas ayuda, responde a este correo y la abrimos de nuevo.",),
        ),
        Text(
            "We closed your request",
            "We closed your request",
            ("Hi, as we did not hear back from you, we closed the request.",),
            closing=("If you still need help, reply to this email and we open it again.",),
        ),
        {"text": ""},
        quote="text",
    ),
    "data_export": Template(
        "Descarga de datos",
        "Cuando el archivo con los datos del usuario está listo.",
        Text(
            "Tus datos de Kuulis",
            "Tus datos están listos",
            (
                "Hola {name}, aquí puedes descargar una copia de tus datos de Kuulis (un archivo "
                "JSON). El enlace vence en 24 horas.",
                "Si no lo pediste, cambia tu contraseña desde la app.",
            ),
            "Descargar mis datos",
        ),
        Text(
            "Your Kuulis data",
            "Your data is ready",
            (
                "Hi {name}, here you can download a copy of your Kuulis data (a JSON file). The "
                "link expires in 24 hours.",
                "If you did not ask for it, change your password in the app.",
            ),
            "Download my data",
        ),
        {"name": "Ana", "link": "https://kuulis.app/descarga-ejemplo"},
    ),
    "account_deletion": Template(
        "Eliminación de cuenta",
        "Cuando el usuario pide eliminar su cuenta.",
        Text(
            "Eliminaremos tu cuenta",
            "Eliminaremos tu cuenta el {date}",
            (
                "Hola {name}, recibimos tu pedido de eliminar tu cuenta de Kuulis.",
                "Si cambias de opinión, entra a la app antes de esa fecha y la cuenta sigue "
                "como estaba.",
            ),
        ),
        Text(
            "We will delete your account",
            "We will delete your account on {date}",
            (
                "Hi {name}, we got your request to delete your Kuulis account.",
                "If you change your mind, sign in to the app before that date and the account "
                "stays as it was.",
            ),
        ),
        {"name": "Ana", "date": "12 de noviembre"},
        {"date": "November 12"},
    ),
}


def _site() -> str:
    return settings.FRONTEND_URL.rstrip("/")


def _fill(template: str, values: dict[str, Any], escape: bool) -> str:
    safe = {k: (html.escape(str(v), quote=True) if escape else str(v)) for k, v in values.items()}
    return template.format_map(_Missing(safe))


class _Missing(dict):
    def __missing__(self, key: str) -> str:
        return ""


def layout(locale: str, heading: str, body_html: str, preheader: str = "") -> str:
    """The branded frame: wordmark, white card, footer with the site."""
    footer = (
        "Recibes este correo por tu cuenta de Kuulis."
        if locale == "es"
        else "You get this email because of your Kuulis account."
    )
    site = html.escape(_site(), quote=True)
    return f"""<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{heading}</title></head>
<body style="margin:0;padding:0;background:{PAPER};">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="background:{PAPER};"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
 style="max-width:560px;">
<tr><td style="padding:0 4px 16px;font-family:Arial,Helvetica,sans-serif;font-size:24px;
font-weight:bold;color:{BRAND};letter-spacing:-0.5px;">Kuulis</td></tr>
<tr><td style="background:#ffffff;border:1px solid {LINE};border-radius:12px;padding:28px 24px;
font-family:Arial,Helvetica,sans-serif;color:{INK};">
<h1 style="margin:0 0 16px;font-size:22px;line-height:28px;font-weight:bold;color:{INK};">
{heading}</h1>
{body_html}
</td></tr>
<tr><td style="padding:16px 4px;font-family:Arial,Helvetica,sans-serif;font-size:12px;
line-height:18px;color:{MUTED};">{footer}<br>
<a href="{site}" style="color:{MUTED};">{site.removeprefix("https://")}</a></td></tr>
</table></td></tr></table></body></html>"""


def _button(label: str, link: str) -> str:
    href = html.escape(link, quote=True)
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" border="0"
 style="margin:8px 0 4px;"><tr><td style="border-radius:8px;background:{BRAND};">
<a href="{href}" style="display:inline-block;padding:12px 22px;font-family:Arial,Helvetica,
sans-serif;font-size:16px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px;">
{html.escape(label)}</a></td></tr></table>
<p style="margin:12px 0 0;font-size:12px;line-height:18px;color:{MUTED};word-break:break-all;">
{href}</p>"""


def render(name: str, locale: str, values: dict[str, Any] | None = None) -> tuple[str, str, str]:
    """(subject, HTML, plain text) of template ``name`` in ``locale`` (Spanish fallback)."""
    template = TEMPLATES[name]
    locale = locale if locale in ("es", "en") else "es"
    text: Text = getattr(template, locale)
    values = dict(values or {})
    subject = _fill(text.subject, values, escape=False)
    heading = _fill(text.heading, values, escape=True)
    paragraphs = [_fill(p, values, escape=True) for p in text.paragraphs]
    body = "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:24px;">{p}</p>' for p in paragraphs
    )
    plain = [_fill(text.heading, values, escape=False), ""]
    plain += [_fill(p, values, escape=False) for p in text.paragraphs]
    quoted = str(values.get(template.quote, "")) if template.quote else ""
    if quoted:
        safe = html.escape(quoted).replace("\n", "<br>")
        body += (
            f'<div style="margin:0 0 14px;padding:12px 14px;border-left:3px solid {BRAND};'
            f'background:{PAPER};font-size:15px;line-height:22px;">{safe}</div>'
        )
        plain += ["", quoted]
    link = values.get("link")
    if text.cta and link:
        body += _button(text.cta, str(link))
        plain += ["", f"{text.cta}: {link}"]
    for paragraph in text.closing:
        body += (
            f'<p style="margin:14px 0 0;font-size:14px;line-height:21px;color:{MUTED};">'
            f"{_fill(paragraph, values, escape=True)}</p>"
        )
        plain += ["", _fill(paragraph, values, escape=False)]
    plain += ["", "Kuulis", _site()]
    preheader = html.escape(_fill(text.paragraphs[0], values, escape=False)[:120])
    return subject, layout(locale, heading, body, preheader), "\n".join(plain)


def sample(name: str, locale: str = "es") -> dict[str, str]:
    template = TEMPLATES[name]
    return dict(template.sample) | (template.sample_en if locale == "en" else {})


async def send_to_user(
    user_id: uuid.UUID | str, name: str, values: dict[str, Any] | None = None
) -> None:
    """Queues template ``name`` to the user's email, in their language."""
    from apps.notifications import tasks

    await tasks.send_user_email.kiq(
        str(user_id), name, {k: str(v) for k, v in (values or {}).items()}
    )
