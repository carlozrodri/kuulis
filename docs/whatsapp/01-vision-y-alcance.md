# 01 · Visión y alcance

**Área:** API · Admin · (Mobile solo para el motorizado: una etiqueta) · **Depende de:** docs de producción 10
(control remoto), 11 (seguridad en el viaje), 13 (soporte), 14 (notificaciones), 15 (cancelaciones), 16 (antifraude)

## Objetivo
Que cualquier persona en Caracas pueda pedir una moto de Kuulis **escribiendo a un número de WhatsApp**, sin
instalar nada ni crear una cuenta. En Venezuela WhatsApp está en todos los teléfonos, incluso en los que no
tienen espacio para otra app o usan datos con cuidado. Pedir por WhatsApp quita la barrera de la descarga del APK
(no hay tiendas todavía) y convierte cada viaje en un cliente que después puede pasar a la app.

## Por qué ahora
- La app se distribuye como APK fuera de la tienda (doc 09 de producción); cada paso de instalación pierde gente.
- El precio fijo y «sin regateo» se explica muy bien en un chat: el bot responde con el precio exacto donde el
  mototaxi de la calle dice «depende».
- El costo es casi cero: las respuestas dentro de la ventana de 24 h no se cobran (ver 04).

## Decidido por Carlos (2026-10-30)
1. Por WhatsApp se puede **pedir viaje, cotizar, ver el estado y cancelar**.
2. Origen y destino se envían con la **ubicación de WhatsApp** (el clip 📎 → Ubicación).
3. **Precio igual que en la app**: tarifa en USD fijada por Kuulis, equivalente en bolívares a tasa **BCV** y
   **Binance**, «precio justo, sin regateo». Recargos por hora o zona y promociones automáticas iguales.
4. **El pago se resuelve entre pasajero y motorizado**, igual que en la app: el pasajero elige el método
   (efectivo $, Pago Móvil, Binance, Zelle, efectivo Bs, según `payment_methods` del admin) y le paga directo.
5. **Se puede pedir sin registrarse.** Al **completar un viaje**, ese teléfono queda guardado en la base de datos
   como **cliente**.
6. **Motorizados: todo sigue por la app.** No usan WhatsApp para nada de Kuulis.
7. **Al pasajero le llegan por WhatsApp todos los avisos**: motorizado asignado, llegó, viaje terminado,
   calificación, y también cancelaciones y «buscando otro motorizado».
8. **El backend de Kuulis recibe el webhook directamente** (sin intermediarios como Twilio o 360dialog).
9. **API oficial de Meta (Cloud API)**, empezando con el número de prueba de Meta.
10. **Solo español.**
11. **Soporte humano en el mismo chat**: el pasajero puede hablar con una persona del equipo por ahí.

## Alcance
### Incluye
- Conversación guiada con botones y listas de WhatsApp (no hace falta escribir comandos).
- Cotizar sin pedir, pedir, ver estado, cancelar con motivo (mismas reglas de gracia y conteo del doc 15).
- Avisos de cada cambio de estado del viaje, con el **PIN de inicio** cuando la ciudad lo exige (doc 11) y el
  **enlace en vivo** (`/public/rides/shared/{token}`) para ver la moto en el mapa.
- Calificación obligatoria del motorizado (1 a 5 y comentario opcional) antes del siguiente viaje, como en la app.
- Reenvío del chat del viaje: el motorizado escribe en la app y el pasajero lo recibe por WhatsApp, y al revés
  (Supuesto, pregunta 4).
- Soporte humano: el chat pasa a un ticket del doc 13 con origen `whatsapp`; el equipo responde desde el admin y
  la respuesta llega por WhatsApp. El bot se pausa mientras tanto.
- Cliente invitado (ver 03) y su conversión a cliente al completar el primer viaje.
- Admin: lista de contactos de WhatsApp, historial de mensajes, bloquear un número, métricas del canal.
- Flag `whatsapp_rides` en el control remoto para encenderlo, apagarlo o abrirlo por porcentaje.

### Fuera (por ahora)
- Motorizados por WhatsApp (decidido: todo por la app).
- Otros idiomas (decidido: solo español).
- Pagos dentro de WhatsApp (WhatsApp Pay no existe en Venezuela; además el pago es directo).
- Mensajes de marketing o campañas por WhatsApp (necesitan otro consentimiento y cuestan; ver 04).
- Pedidos para otra persona, paradas intermedias, programar viajes, lugares guardados: se evalúan después
  con datos de uso.
- Unir el invitado con una cuenta de la app (pregunta 9).
- Notas de voz como entrada (no se transcriben; el bot pide usar los botones).

## Qué se reutiliza (no se duplica lógica)
| Pieza | Dónde vive hoy | Uso desde WhatsApp |
| --- | --- | --- |
| Cotización, recargos, promociones automáticas, tasas BCV/Binance | `rides.services.create_quote`, `rides.pricing`, `zones`, `rates` | Igual, con el usuario invitado |
| Crear viaje, una sola solicitud activa, calificación pendiente | `rides.services.create_ride` | Igual |
| Despacho a motorizados | `rides.dispatch` | Sin cambios |
| Cancelar con motivo y reglas de gracia | `rides.services.cancel` | Igual |
| Zonas de servicio, horario, ciudades | `config.area_at`, `control.ensure_open`, `zones.ensure_allowed` | Igual; los códigos de error se traducen a mensajes del bot |
| Suspensiones, pausas por calidad, riesgo | `moderation`, `quality`, `risk` | Igual, sobre el usuario invitado y además por número |
| Enlace en vivo | `safety` (`POST /rides/{id}/share`) | Se crea solo al asignar motorizado |
| Avisos | `rides.notify` (push) | Nuevo canal: si el pasajero es de WhatsApp, el aviso sale por WhatsApp |
| Tickets de soporte | `moderation.Report` + `support.conversation` | Nuevo origen `whatsapp` |
| Reverso de dirección | `geo.reverse` (Photon propio) | Para mostrar la dirección de la ubicación recibida |

## Métricas de éxito (Supuesto)
- **Conversión cotización → viaje pedido** por WhatsApp ≥ la de la app.
- **Viajes completados por WhatsApp** por semana y % del total.
- **Clientes nuevos** (primer viaje completado) que llegaron por WhatsApp.
- **Tiempo de respuesta del bot** (webhook recibido → respuesta enviada) p95 < 2 s.
- **Errores de envío** a WhatsApp < 1 % y calidad del número en **verde** (Meta).
- **Paso a la app**: invitados que luego instalan la app (cuando exista la unión, pregunta 9).

## Costo esperado
- Infraestructura: ninguna nueva. Corre en la API y el worker que ya existen.
- Meta: los mensajes de servicio (respuestas mientras la ventana de 24 h está abierta) **no se cobran**. Casi todo
  el flujo de un viaje ocurre dentro de esa ventana porque el pasajero acaba de escribir. Solo se pagarían
  plantillas fuera de la ventana (respuesta de soporte tardía, objeto perdido). Detalle en 04.
- Sin proveedor intermediario (decidido 8), así que no hay cuota mensual.
