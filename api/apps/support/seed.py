"""Starter help center articles (doc 13), inserted once by the migration. The team edits them
from the admin afterwards; this file is not read again."""

# (slug, topic, audience, position, {locale: (title, body_md)})
ARTICLES: list[tuple[str, str, str, int, dict[str, tuple[str, str]]]] = [
    (
        "como-pedir-un-viaje",
        "rides",
        "passenger",
        1,
        {
            "es": (
                "Cómo pedir un viaje",
                "1. Abre Kuulis y escribe a dónde vas.\n"
                "2. Revisa el precio y el método de pago.\n"
                "3. Toca **Pedir moto**. Te avisamos cuando un motorizado acepte.\n\n"
                "El precio que ves al pedir es el que pagas: queda guardado en el viaje.",
            ),
            "en": (
                "How to request a ride",
                "1. Open Kuulis and type where you are going.\n"
                "2. Check the price and the payment method.\n"
                "3. Tap **Request moto**. We let you know when a driver accepts.\n\n"
                "The price you see when you request is the price you pay: it is saved with the "
                "ride.",
            ),
        },
    ),
    (
        "como-pago-al-motorizado",
        "payments",
        "all",
        1,
        {
            "es": (
                "Cómo se paga el viaje",
                "En Kuulis le pagas **directamente al motorizado**, con el método que eligieron "
                "(efectivo, pago móvil, Binance o Zelle). Kuulis no cobra comisión por viaje.\n\n"
                "El monto es el precio que muestra la app. Si te cobraron distinto, entra al "
                "viaje y toca **Necesito ayuda con este viaje → Me cobraron distinto**.",
            ),
            "en": (
                "How rides are paid",
                "In Kuulis you pay **the driver directly**, with the method you chose (cash, pago "
                "móvil, Binance or Zelle). Kuulis takes no commission per ride.\n\n"
                "The amount is the price the app shows. If you were charged differently, open the "
                "ride and tap **I need help with this ride → I was charged differently**.",
            ),
        },
    ),
    (
        "olvide-un-objeto",
        "rides",
        "passenger",
        2,
        {
            "es": (
                "Olvidé algo en la moto",
                "Entra a **Viajes**, abre el viaje y toca **Necesito ayuda con este viaje → "
                "Olvidé un objeto**. Describe lo que olvidaste.\n\n"
                "Le avisamos al motorizado. Si lo tiene, se abre el chat del viaje para que "
                "acuerden la entrega sin compartir teléfonos.",
            ),
            "en": (
                "I left something on the moto",
                "Go to **Rides**, open the ride and tap **I need help with this ride → I left "
                "something**. Describe what you left.\n\n"
                "We tell the driver. If they have it, the ride chat opens so you can arrange the "
                "hand-over without sharing phone numbers.",
            ),
        },
    ),
    (
        "seguridad-en-el-viaje",
        "safety",
        "all",
        1,
        {
            "es": (
                "Tu seguridad en el viaje",
                "- Revisa que la placa y la moto coincidan con las de la app.\n"
                "- En algunas ciudades el motorizado te pide un **PIN** para empezar.\n"
                "- Comparte tu viaje en vivo con tus **contactos de confianza**.\n"
                "- Si estás en peligro, toca **SOS**: llama a emergencias y avisa a tus "
                "contactos.",
            ),
            "en": (
                "Your safety on the ride",
                "- Check that the plate and the moto match the ones in the app.\n"
                "- In some cities the driver asks for a **PIN** to start.\n"
                "- Share your live ride with your **trusted contacts**.\n"
                "- If you are in danger, tap **SOS**: it calls emergencies and alerts your "
                "contacts.",
            ),
        },
    ),
    (
        "no-puedo-entrar",
        "account",
        "all",
        1,
        {
            "es": (
                "No puedo entrar a mi cuenta",
                "Toca **Olvidé mi contraseña** en la pantalla de inicio y sigue el enlace que te "
                "llega por correo. Revisa también la carpeta de spam.\n\n"
                "Si aún no puedes entrar, escríbenos desde el formulario de contacto de la web.",
            ),
            "en": (
                "I cannot sign in",
                "Tap **Forgot password** on the sign-in screen and follow the link we email you. "
                "Check your spam folder too.\n\n"
                "If you still cannot sign in, write to us with the contact form on the website.",
            ),
        },
    ),
    (
        "cuota-mensual",
        "wallet",
        "driver",
        1,
        {
            "es": (
                "La cuota mensual del motorizado",
                "Kuulis no cobra comisión por viaje. Pagas una **cuota mensual solo en los meses "
                "en que haces viajes**, según lo que ganaste ese mes. Los primeros meses son "
                "gratis.\n\n"
                "La cuota se descuenta de tu **billetera**. Recárgala desde **Billetera → "
                "Recargar** y revisa ahí el detalle de cada cobro.",
            ),
            "en": (
                "The driver's monthly fee",
                "Kuulis takes no commission per ride. You pay a **monthly fee only in the months "
                "you do rides**, based on what you earned that month. The first months are free."
                "\n\nThe fee is taken from your **wallet**. Top it up from **Wallet → Top up** and "
                "see each charge there.",
            ),
        },
    ),
    (
        "documentos-y-vencimientos",
        "documents",
        "driver",
        1,
        {
            "es": (
                "Documentos y vencimientos",
                "En **Perfil → Mis documentos** ves el estado de cada documento y cuándo vence. "
                "Te avisamos 30, 7 y 1 día antes.\n\n"
                "Si un documento vence, no puedes conectarte hasta subir el nuevo. Súbelo desde "
                "**Mis documentos → Renovar**; el anterior sigue valiendo mientras lo revisamos.",
            ),
            "en": (
                "Documents and expiry dates",
                "In **Profile → My documents** you see the status of each document and when it "
                "expires. We remind you 30, 7 and 1 day before.\n\n"
                "If a document expires you cannot go online until you upload the new one. Upload "
                "it from **My documents → Renew**; the old one stays valid while we review it.",
            ),
        },
    ),
    (
        "selfie-de-verificacion",
        "documents",
        "driver",
        2,
        {
            "es": (
                "¿Por qué me piden una selfie?",
                "De vez en cuando, al conectarte, te pedimos una **selfie en vivo** para confirmar "
                "que eres tú quien maneja. Toma la foto con buena luz y sin lentes oscuros ni "
                "casco. Puedes conectarte apenas la envías.",
            ),
            "en": (
                "Why am I asked for a selfie?",
                "From time to time, when you go online, we ask for a **live selfie** to confirm "
                "you are the one driving. Take it in good light, without sunglasses or helmet. "
                "You can go online as soon as you send it.",
            ),
        },
    ),
    (
        "la-app-no-funciona",
        "app",
        "all",
        1,
        {
            "es": (
                "La app no carga o se cierra",
                "1. Revisa tu conexión a internet.\n"
                "2. Cierra la app por completo y ábrela de nuevo: así baja las actualizaciones.\n"
                "3. Si usas Android, instala la última versión desde la web de Kuulis.\n\n"
                "Si sigue fallando, escríbenos desde **Ayuda → Contactar a soporte** y cuéntanos "
                "qué pasa.",
            ),
            "en": (
                "The app does not load or closes",
                "1. Check your internet connection.\n"
                "2. Close the app completely and open it again: that is how it gets updates.\n"
                "3. On Android, install the latest version from the Kuulis website.\n\n"
                "If it keeps failing, write to us from **Help → Contact support** and tell us "
                "what happens.",
            ),
        },
    ),
]
