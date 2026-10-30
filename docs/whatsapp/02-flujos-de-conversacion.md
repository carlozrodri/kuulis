# 02 · Flujos de conversación

Cómo habla el bot de Kuulis por WhatsApp. Todo en **español** (decidido), con la voz venezolana de nivel medio
que se aprobó para la app (`docs/product/wow/05-voz-y-mensaje.md`): cercana, clara, sin exagerar la jerga. Los
textos son propuestas y viven en un solo catálogo (`apps/whatsapp/texts.py`) para poder ajustarlos sin tocar la
lógica.

## Principios
- **Botones antes que texto.** Cada paso ofrece botones de respuesta (máximo 3 por mensaje, título de 20
  caracteres) o una lista (hasta 10 filas). El texto libre solo se usa para el nombre, el motivo «Otro» y el
  soporte.
- **Palabras clave siempre activas**, en cualquier momento y sin importar mayúsculas ni tildes: `menú`, `cotizar`,
  `pedir`, `estado`, `cancelar`, `soporte`, `ayuda`. Si no se entiende un mensaje, el bot muestra el menú.
- **Un mensaje, una idea.** Mensajes cortos; el precio siempre con el mismo formato.
- **Nunca un callejón sin salida.** Todo error termina con qué hacer y el botón de soporte.
- **Idempotente.** Si el pasajero toca dos veces el mismo botón o WhatsApp reenvía el webhook, no se crean dos
  viajes (ver 03).

## Estados de la conversación
Viven en Redis por número (`wa:conv:{wa_id}`), con vencimiento; el viaje real vive en Postgres.

| Estado | Espera | Vence | Al vencer |
| --- | --- | --- | --- |
| `idle` | Cualquier cosa | — | — |
| `ask_name` | El nombre (texto) | 30 min | Vuelve a `idle` |
| `ask_pickup` | Ubicación de origen | 30 min | Vuelve a `idle` |
| `ask_dropoff` | Ubicación de destino | 30 min | Vuelve a `idle` |
| `quoted` | «Pedir», «Cambiar» o «Cancelar» | `quote_ttl_seconds` (300 s) | «La cotización venció» + botón «Cotizar de nuevo» |
| `ask_payment` | Método de pago (lista) | `quote_ttl_seconds` | Igual que `quoted` |
| `in_ride` | Botones del viaje, chat al motorizado | Mientras el viaje esté activo | — |
| `ask_rating` | Estrellas (lista) y comentario opcional | Hasta calificar | Recordatorio (ver avisos) |
| `ask_cancel_reason` | Motivo (lista) | 5 min | Vuelve a `in_ride` |
| `support` | Texto y fotos para el equipo | Hasta que el ticket se cierre | Vuelve a `idle` |

La fuente de verdad del viaje es la base de datos: al recibir cualquier mensaje, el bot primero mira si el
pasajero tiene un viaje activo (`get_active`) o una calificación pendiente (`get_pending_rating`) y corrige el
estado de Redis si quedó desfasado.

## Flujo 1 · Primer mensaje
Pasajero: «Hola» (o cualquier cosa).

> 👋 ¡Hola! Soy Kuulis, motos en Caracas con **precio justo, sin regateo**. El precio lo ves antes de pedir y va
> completo para tu motorizado.
>
> Al escribirnos aceptas los Términos y la Política de privacidad: {enlace a /legal de la web}
>
> [Pedir una moto] [Cotizar] [Soporte]

- La primera vez se guarda el consentimiento (`consent_at`, versión del texto legal, doc 07 de producción).
- Si el número no es venezolano (+58) y se decide así (pregunta 1): «Por ahora Kuulis solo atiende números de
  Venezuela.» y [Soporte].
- Si el número está bloqueado: no se responde nada más que una vez «Este número no puede pedir viajes. Escribe
  *soporte* si crees que es un error.»

## Flujo 2 · Nombre (solo antes del primer viaje, Supuesto: pregunta 2)
> ¿Cómo te llamas? Así te va a saludar tu motorizado. (Solo tu nombre)

- Se acepta de 2 a 40 caracteres, sin enlaces ni números de teléfono; se guarda en el usuario invitado.
- Si responde algo inválido: «Escríbeme solo tu nombre, por ejemplo: *María*.»

## Flujo 3 · Cotizar y pedir
1. **Origen.** El bot envía un *mensaje de solicitud de ubicación* (botón nativo «Enviar ubicación»):
   > 📍 ¿Dónde te buscamos? Toca *Enviar ubicación* y elige el punto exacto de recogida.
   - Si el pasajero envía una ubicación (actual o elegida en el mapa), se toman `latitude` y `longitude`; la
     dirección viene de `name`/`address` del mensaje o, si no trae, de `geo.reverse`.
   - Si escribe una dirección: Supuesto (pregunta 5). Con la recomendada, se busca con `geo.search`, se
     devuelven hasta 3 resultados en una lista y se confirma; si no, se le explica cómo enviar la ubicación.
   - Fuera de zona (`outside_service_area`): «Todavía no llegamos ahí. Por ahora atendemos Caracas.»
2. **Destino.** Mismo mensaje: «🏁 ¿A dónde vas? Envía la ubicación del destino.»
3. **Cotización.** Se llama a `create_quote` con el usuario invitado y `vehicle_type = moto`. Respuesta:
   > 🏍️ Tu viaje en moto
   > Desde: Av. Francisco de Miranda, Chacao
   > Hasta: Plaza Venezuela
   > 5,2 km · unos 14 min
   >
   > **$2,50** · Bs 98,75 (BCV) · Bs 112,00 (Binance)
   > Precio justo, sin regateo. Los $2,50 van completos para tu motorizado.
   >
   > [Pedir] [Cambiar] [Cancelar]
   - Si hay recargo: una línea «Tarifa alta por demanda (x1,2)» como en la app.
   - Si hay promoción automática: «Promo *Nombre*: −$0,50. Pagas **$2,00**.»
   - «Cotizar» desde el menú termina aquí; «Pedir» continúa.
4. **Método de pago.** Lista con los métodos de `config.payment_methods` (en el orden del admin):
   > ¿Cómo le vas a pagar a tu motorizado? Le pagas directo al llegar.
   > [Ver métodos ▸] Efectivo $ · Pago Móvil · Binance · Zelle · Efectivo Bs
   - Supuesto: se recuerda el último método usado y se ofrece como primer botón «Igual que la vez pasada».
5. **Nota para el motorizado (opcional).** Botones [Sin nota] [Agregar nota]. La nota va al campo `note` (140).
6. **Confirmar y pedir.** Se llama a `create_ride` con el `quote_id`:
   > ✅ ¡Listo! Estamos buscando tu motorizado. Te aviso por aquí apenas uno acepte.
   > [Ver estado] [Cancelar]

Errores de `create_ride` que se traducen:
| Código | Mensaje |
| --- | --- |
| `quote_expired` | «La cotización venció (pasaron 5 minutos). ¿Te la hago de nuevo?» [Cotizar de nuevo] |
| `ride_already_active` | «Ya tienes un viaje en curso.» + resumen de estado |
| `rating_required` | «Antes de pedir otro, califica tu último viaje.» + lista de estrellas |
| `outside_service_area` / zona restringida | «Todavía no llegamos ahí.» |
| Servicio cerrado (`control.ensure_open`) | El mensaje de cierre configurado en el admin |
| Suspensión / pausa por calidad | El mismo texto que da la app, con fecha si la hay, y [Soporte] |
| `payment_method_invalid` | Se vuelve a mostrar la lista |

## Flujo 4 · Avisos del viaje
Llegan sin que el pasajero escriba. Todos con los botones [Ver estado] [Cancelar] [Soporte] mientras aplique.

| Evento | Mensaje |
| --- | --- |
| Asignado | «🏍️ *Pedro* aceptó tu viaje. Moto Bera SBR negra, placa **AB1C23D**. Llega en unos 4 min. ⭐ 4,9. Míralo en el mapa: {enlace en vivo}» + foto del motorizado como imagen (Supuesto) |
| PIN (si la ciudad lo usa) | «Tu código para empezar el viaje es **4821**. Dáselo a Pedro solo cuando estés en la moto.» |
| Reasignando | «Pedro tuvo que cancelar. Ya estamos buscando otro motorizado, no tienes que hacer nada.» |
| Llegó | «📍 Pedro llegó al punto de recogida. Busca la placa **AB1C23D**.» |
| En curso | «¡Buen viaje! Puedes seguir el recorrido aquí: {enlace en vivo}» |
| Terminado | «🏁 Llegaste. Págale **$2,50** a Pedro con *Pago Móvil*. Todo es para él.» y enseguida la calificación |
| Sin motorizados | «No encontramos motorizado cerca. Intenta de nuevo en unos minutos.» [Pedir de nuevo] |
| No llegaste (no_show) | «Pedro te esperó y no llegaste al punto de recogida, así que el viaje se canceló.» |
| Cancelado por Kuulis | «Kuulis canceló el viaje. Si necesitas ayuda escribe *soporte*.» |
| Cancelado por el motorizado (sin reasignar) | «El motorizado canceló el viaje. Puedes pedir otro.» [Pedir de nuevo] |

Los textos salen de los mismos eventos que hoy envían push (`rides.notify.TEMPLATES`), con su versión para
WhatsApp. Ver 03 para cómo se enrutan.

## Flujo 5 · Ver estado
«estado» o [Ver estado]:
- Sin viaje: «No tienes viajes activos.» [Pedir una moto]
- Buscando: «Buscando motorizado desde hace 1 min…» [Cancelar]
- Con motorizado: nombre, moto, placa, distancia o tiempo estimado y el enlace en vivo.

## Flujo 6 · Cancelar
«cancelar» o [Cancelar]:
1. Si el motorizado ya fue asignado y pasó la gracia (`passenger_cancel_grace_s`), se avisa antes: «Pedro ya va
   en camino. Si cancelas ahora cuenta en tu historial.» [Sí, cancelar] [No]
2. Lista de motivos (`PASSENGER_REASONS`): Tardaba mucho · Cambié de planes · El motorizado me pidió cancelar ·
   La moto no coincide · Punto de recogida equivocado · Otro (pide texto).
3. Se llama a `rides.services.cancel` con el código. «Listo, cancelamos tu viaje.» [Pedir una moto]

«La moto no coincide» abre además el reporte de `vehicle_mismatch`, igual que en la app.

## Flujo 7 · Calificar (obligatorio)
Al terminar:
> ¿Cómo estuvo tu viaje con Pedro?
> [Calificar ▸] ⭐⭐⭐⭐⭐ Excelente · ⭐⭐⭐⭐ Bien · ⭐⭐⭐ Regular · ⭐⭐ Mal · ⭐ Muy mal

Después: «¿Quieres dejarle un comentario?» [Sin comentario] [Escribir]. Se llama a `rides.services.rate`. Con 1
o 2 estrellas se ofrece [Reportar un problema] que abre soporte con el viaje como contexto.

Mientras no califique, cualquier intento de pedir muestra primero la calificación (misma regla que la app).

## Flujo 8 · Chat con el motorizado (Supuesto: pregunta 4)
- Mientras el viaje esté asignado, lo que el pasajero escriba (que no sea palabra clave) se envía al chat del
  viaje (`rides.services.post_message`) y el motorizado lo ve en la app.
- Lo que el motorizado escriba en la app llega por WhatsApp como «💬 *Pedro*: Ya voy llegando».
- Al terminar el viaje el chat se cierra (`chat_closed`) y lo escrito vuelve al menú.
- Fotos y notas de voz del pasajero no se reenvían: «Por ahora solo puedo pasarle texto a tu motorizado.»

## Flujo 9 · Soporte humano (decidido 11)
«soporte», «ayuda», «hablar con alguien» o [Soporte]:
1. Si hay un viaje activo o reciente (24 h), botones para elegir el tema: [Sobre mi viaje] [Otro tema].
2. «Cuéntanos qué pasó. Una persona del equipo te responde por aquí.» Se crea un ticket (`moderation.Report`)
   con `source = whatsapp`, la categoría elegida y el viaje si aplica.
3. **El bot se pausa** para ese número (`support`): todo lo que el pasajero escriba, incluidas fotos, se agrega al
   ticket como mensaje del usuario. Las palabras `cancelar` y `estado` siguen funcionando si hay un viaje activo,
   por seguridad.
4. El equipo responde desde el admin (pantalla de tickets del doc 13); la respuesta sale por WhatsApp como «🧑‍💼
   *Ana de Kuulis*: …». Si la ventana de 24 h se cerró, sale la plantilla `soporte_respuesta` (ver 04).
5. Al resolver el ticket: «Cerramos tu conversación. Si necesitas algo más, escríbenos.» y el bot vuelve.
   Escribir `menú` también sale del modo soporte (el ticket sigue abierto para el equipo).
6. Horario: fuera del horario de soporte configurado se dice cuándo responderán; los tiempos de respuesta (SLA)
   son los del doc 13.

**Emergencias:** si el texto contiene palabras de riesgo (accidente, robo, me siguen, emergencia), el bot
responde de inmediato con los números de emergencia configurados en el doc 11 y marca el ticket como urgente.

## Mensajes que el bot no entiende
- Texto libre fuera de contexto: menú principal.
- Nota de voz, video, sticker, documento, contacto: «Por ahora no puedo leer eso. Usa los botones o escribe
  *soporte*.»
- Reacciones y confirmaciones de lectura: se ignoran.
- Mensaje editado o eliminado por el usuario: se ignora (se guarda en el registro).

## Ejemplo completo
```
Pasajero: hola
Kuulis:   👋 ¡Hola! Soy Kuulis… [Pedir una moto] [Cotizar] [Soporte]
Pasajero: (toca Pedir una moto)
Kuulis:   ¿Cómo te llamas? …
Pasajero: María
Kuulis:   📍 ¿Dónde te buscamos? [Enviar ubicación]
Pasajero: (ubicación: Chacao)
Kuulis:   🏁 ¿A dónde vas? [Enviar ubicación]
Pasajero: (ubicación: Plaza Venezuela)
Kuulis:   🏍️ Tu viaje en moto … $2,50 · Bs 98,75 (BCV) … [Pedir] [Cambiar] [Cancelar]
Pasajero: (toca Pedir)
Kuulis:   ¿Cómo le vas a pagar? [Ver métodos ▸]
Pasajero: (elige Pago Móvil)
Kuulis:   ¿Alguna nota para tu motorizado? [Sin nota] [Agregar nota]
Pasajero: (toca Sin nota)
Kuulis:   ✅ ¡Listo! Estamos buscando tu motorizado…
Kuulis:   🏍️ Pedro aceptó tu viaje… {enlace}
Kuulis:   📍 Pedro llegó…
Kuulis:   🏁 Llegaste. Págale $2,50 a Pedro con Pago Móvil…
Kuulis:   ¿Cómo estuvo tu viaje con Pedro? [Calificar ▸]
```
