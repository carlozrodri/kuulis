# Pedir viajes por WhatsApp

Diseño para que un pasajero pida, cotice, siga y cancele un viaje de Kuulis **desde WhatsApp**, sin instalar la
app, usando la **API oficial de WhatsApp Business (Meta Cloud API)**. Solo documentos: no hay código todavía.

**Estado: propuesto (2026-10-30).** Convención de siempre: lo que dijo Carlos es **Decidido**; el resto es
**Supuesto** y se valida antes de construir. Las preguntas abiertas están al final de este archivo.

| Doc | Qué contiene |
| --- | --- |
| [01 · Visión y alcance](01-vision-y-alcance.md) | Para qué, qué entra y qué no, decisiones de Carlos, métricas, costo |
| [02 · Flujos de conversación](02-flujos-de-conversacion.md) | Cada conversación paso a paso, textos en español, botones, errores, soporte humano |
| [03 · Arquitectura y webhook](03-arquitectura-y-webhook.md) | App `apps/whatsapp`, webhook, colas, estado, cliente invitado, avisos del viaje, datos |
| [04 · Plantillas y cumplimiento de Meta](04-plantillas-y-cumplimiento-meta.md) | Ventana de 24 h, plantillas, políticas, verificación del negocio, calidad del número, precios |
| [05 · Seguridad y variables de entorno](05-seguridad-y-variables.md) | Token, firma `X-Hub-Signature-256`, rotación, abuso, privacidad, variables |
| [06 · Pruebas y salida a producción](06-pruebas-y-produccion.md) | Pruebas automáticas, QA con el número de prueba, lista de salida, monitoreo, vuelta atrás |

## Resumen en cinco líneas
1. El pasajero escribe al número de Kuulis, comparte su **ubicación de WhatsApp** como origen y otra como destino,
   y recibe el **mismo precio que en la app** (USD fijo, equivalente en Bs a tasa BCV y Binance, sin regateo).
2. Elige cómo le pagará al motorizado, confirma con un botón y el viaje entra al **mismo despacho** que los de la
   app. Los motorizados no notan diferencia salvo una etiqueta «Pedido por WhatsApp».
3. Todos los avisos del viaje (asignado, llegó, en curso, terminado, calificación, cancelaciones) le llegan por
   WhatsApp, con un enlace para ver al motorizado en el mapa en vivo.
4. No necesita registrarse: el viaje usa un **cliente invitado** ligado a su número, que pasa a ser **cliente**
   en la base de datos cuando completa su primer viaje.
5. Escribiendo «soporte» habla con una persona del equipo **en el mismo chat**; el equipo responde desde el admin.

## Orden de construcción propuesto
| Paso | Qué | Docs |
| --- | --- | --- |
| W1 | App `apps/whatsapp`: webhook con firma, registro de mensajes, cliente de la Graph API, variables | 03, 05 |
| W2 | Conversación de cotizar y pedir (estado en Redis, cliente invitado, reutiliza `create_quote` / `create_ride`) | 02, 03 |
| W3 | Avisos del viaje por WhatsApp, enlace en vivo, PIN, calificación, cancelar, estado | 02, 03 |
| W4 | Soporte humano: tickets con origen `whatsapp`, respuestas desde el admin, pausa del bot | 02, 03 |
| W5 | Admin: contactos de WhatsApp, bloqueo, métricas; plantillas aprobadas en Meta | 03, 04 |
| W6 | QA con el número de prueba, pruebas de carga del webhook y salida a producción con el flag | 06 |

Cada paso entra por PR a `qa`, como siempre. El canal entero queda detrás del flag `whatsapp_rides` del control
remoto (doc 10 de producción), así que se puede apagar sin desplegar.

## Preguntas para Carlos
Cada una con la opción recomendada (⭐). Mientras no respondas, se construye con la recomendada.

1. **Números aceptados**: ⭐ solo números venezolanos (+58) para pedir viajes; otros reciben un mensaje amable /
   cualquier país.
2. **Nombre del pasajero**: ⭐ preguntarlo una sola vez antes del primer viaje («¿Cómo te llamas?») porque el
   nombre de perfil de WhatsApp a veces es un emoji o un apodo / usar el nombre de perfil tal cual.
3. **Teléfono visible para el motorizado**: ⭐ no, igual que en la app (sin llamadas; chat por Kuulis) / sí,
   para que lo llame.
4. **Chat motorizado ↔ pasajero**: ⭐ sí, los mensajes que el motorizado escribe en la app le llegan por WhatsApp
   y lo que el pasajero responde durante el viaje le llega al motorizado en la app / no, solo avisos.
5. **Dirección escrita además de la ubicación**: ⭐ aceptar también una dirección escrita como respaldo
   (buscador propio, se confirma con un mapa) / solo ubicación de WhatsApp, como dijiste.
6. **Invitados que nunca completan un viaje**: ⭐ se borran a los 30 días / se guardan igual.
7. **Número de producción**: ⭐ un número venezolano nuevo, solo para la API (no puede estar en la app de
   WhatsApp) / reutilizar el de soporte (pierde la app de WhatsApp en ese teléfono).
8. **Códigos promocionales por WhatsApp**: ⭐ más adelante (W5+) / desde el inicio.
9. **Unir el invitado con una cuenta de la app**: ⭐ más adelante, verificando el número con un código por
   WhatsApp / desde el inicio.
