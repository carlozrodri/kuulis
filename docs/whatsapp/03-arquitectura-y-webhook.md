# 03 · Arquitectura y webhook

Cómo se construye el canal dentro del monorepo, siguiendo `docs/conventions.md`: una app nueva `api/apps/whatsapp/`
con routers finos, la lógica en servicios y todo lo lento en tareas de Taskiq. **No se duplica nada** de viajes:
el bot es otro «cliente» de los mismos servicios que usa la app.

## Vista general
```
WhatsApp (pasajero)
   │  mensaje
   ▼
Meta Cloud API ──POST webhook (firmado)──► NPM ► Traefik ► API  /api/v1/whatsapp/webhook
                                                              │ 1. verifica X-Hub-Signature-256
                                                              │ 2. descarta duplicados (wamid)
                                                              │ 3. guarda y encola  → 200 OK en < 100 ms
                                                              ▼
                                                     Redis Streams (Taskiq)
                                                              ▼
                                                   Worker: whatsapp.process_inbound
                                                     · candado por número (orden)
                                                     · máquina de estados (Redis)
                                                     · rides.services (cotizar, pedir, cancelar, calificar)
                                                     · support (tickets)
                                                              ▼
                                                   Worker: whatsapp.send ──► Graph API /{PHONE_NUMBER_ID}/messages
                                                              ▲
     rides.events (asignado, llegó, terminado…) ───────────────┘  (en vez de push si el pasajero es de WhatsApp)
     admin (respuesta de soporte) ─────────────────────────────┘
```

Decidido: el backend recibe el webhook directamente (sin proveedor intermedio). La API ya está publicada con TLS
detrás de Nginx Proxy Manager y Traefik (memoria `kuulis-proxy-chain`), que es lo que exige Meta.

## Estructura de la app
```
api/apps/whatsapp/
  router.py        GET y POST /whatsapp/webhook; rutas del admin (/admin/whatsapp/…)
  signature.py     verificación HMAC-SHA256 del cuerpo crudo
  parser.py        convierte el JSON de Meta en eventos tipados (InboundMessage, StatusUpdate…)
  client.py        cliente httpx de la Graph API: send_text, send_buttons, send_list,
                   send_location_request, send_template, send_image, mark_read, get_media
  conversation.py  máquina de estados del flujo (02); solo decide, no hace E/S de red
  texts.py         catálogo de textos en español
  services.py      contactos, invitados, registro de mensajes, bloqueo, enrutamiento de avisos
  notices.py       traduce eventos de viaje a mensajes de WhatsApp
  tasks.py         process_inbound, send, process_status, purge_guests, purge_messages
  models.py        WhatsAppContact, WhatsAppMessage
  schemas.py
  tests/
```
Se registra en `kuulis/urls.py` y sus tareas en la lista de módulos del worker (`manage.py worker`).

## Webhook
### Verificación (GET)
Meta llama una vez al configurar el webhook:
`GET /api/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`
- Si `hub.mode == "subscribe"` y `hub.verify_token` coincide (comparación de tiempo constante) con
  `WHATSAPP_VERIFY_TOKEN`, se responde `200` con `hub.challenge` en texto plano. Si no, `403`.

### Recepción (POST)
1. Leer el **cuerpo crudo** (antes de parsear JSON) con un límite de 1 MB.
2. Verificar `X-Hub-Signature-256` con `WHATSAPP_APP_SECRET` (ver 05). Sin firma o firma mala → `401` y log.
3. Parsear `entry[].changes[]` con `field == "messages"`:
   - `value.metadata.phone_number_id` debe ser `WHATSAPP_PHONE_NUMBER_ID`; si no, se ignora (200).
   - `value.contacts[]` trae `wa_id` y `profile.name`.
   - `value.messages[]`: mensajes entrantes (`text`, `location`, `interactive.button_reply`,
     `interactive.list_reply`, `image`, `audio`, `button`, etc.).
   - `value.statuses[]`: estado de los enviados (`sent`, `delivered`, `read`, `failed` con `errors[]`).
4. Por cada mensaje: `SET wa:seen:{wamid} NX EX 172800`. Si ya existía, es un reintento de Meta y se ignora.
5. Insertar en `whatsapp_messages` (con `wamid` único, por si Redis se perdió) y encolar
   `process_inbound.kiq(message_id)`. Por cada estado, encolar `process_status.kiq(...)`.
6. Responder `200` siempre que la firma sea válida, aunque el contenido no interese. Meta reintenta durante días
   si no recibe 200, y un webhook lento o fallido baja la confianza en el número.

El endpoint queda **fuera del límite de uso por IP por defecto** (Meta envía ráfagas desde pocas IPs) pero con su
propio límite alto (por ejemplo 3000/min) y la firma como control de acceso. Sin autenticación JWT.

### Orden y concurrencia
- Meta no garantiza el orden de entrega. `process_inbound` toma un **candado por número** en Redis
  (`wa:lock:{wa_id}`, 30 s) para que los mensajes de una persona se procesen de a uno, y descarta mensajes con
  `timestamp` más viejo que el último procesado de ese número si cambiarían el estado (por ejemplo una ubicación
  vieja que llega tarde).
- Pedir un viaje es idempotente por dos vías: el `quote_id` es de un solo uso y el índice único
  `uq_rides_active_passenger` impide dos viajes activos. Un doble toque en «Pedir» devuelve el estado del viaje ya
  creado.

## Estado de la conversación
- `wa:conv:{wa_id}` en Redis: `{"state": "quoted", "pickup": {...}, "dropoff": {...}, "quote_id": "...",
  "payment_method": null, "expires_at": "..."}` con TTL según el estado (tabla en 02).
- `conversation.py` es una función pura `handle(state, event, contexto) -> (nuevo_estado, acciones)`; las
  acciones (llamar a `create_quote`, enviar mensajes) las ejecuta `services.py`. Así se prueba sin red.
- La base de datos manda: antes de decidir, se consulta viaje activo y calificación pendiente del invitado.

## El cliente invitado (decidido 5)
`rides.passenger_id` apunta a `users`, y todos los servicios de viajes, calidad, antifraude y suspensiones
trabajan con un `User`. En lugar de abrir otro camino («viaje sin usuario»), cada número de WhatsApp obtiene un
**usuario invitado**:

| Momento | Qué pasa |
| --- | --- |
| Primer mensaje | Se crea `whatsapp_contacts` (número, nombre de perfil, consentimiento). Aún no hay usuario. |
| Primera cotización | Se crea un `User` invitado: `is_guest = true`, `signup_source = whatsapp`, `phone = +58…`, `full_name` = nombre dado (02, flujo 2), sin contraseña ni login posible, email técnico no enrutable `wa-{id}@guest.kuulis.invalid` (el campo es obligatorio y único). Se liga al contacto. |
| Viajes | Exactamente como un pasajero de la app: una solicitud activa, calificación obligatoria, cancelaciones que cuentan, pausas y suspensiones. |
| **Primer viaje completado** | El invitado pasa a **cliente**: `customer_since = now()`. Su teléfono queda guardado. Aparece en el admin como cliente con origen WhatsApp y cuenta en las métricas de clientes nuevos. |
| 30 días sin completar un viaje (pregunta 6) | Tarea `purge_guests`: si no tiene viajes, se borra el usuario; si tiene viajes cancelados (la FK es `RESTRICT`), se anonimiza (sin teléfono ni nombre) como en el borrado de cuentas existente. |

Reglas:
- Ningún envío de email va a dominios `.invalid` (filtro en `apps.notifications.emails`).
- El usuario invitado nunca puede iniciar sesión (sin contraseña, sin cuentas sociales; el login lo rechaza
  explícitamente por `is_guest`).
- Un número = un invitado. Si el mismo teléfono ya es cliente, se reutiliza.
- Más adelante (pregunta 9) un usuario de la app podrá reclamar su historial verificando el número.

## Avisos del viaje por WhatsApp
Hoy `rides.events` publica por WebSocket y envía push con `rides.notify.push`. Se agrega un paso de
enrutamiento por canal:

- `rides.notify.push(user_id, …)` consulta (con caché en Redis) si el destinatario es un invitado de WhatsApp. Si
  lo es, en vez de `send_push` encola `whatsapp.tasks.send_ride_notice.kiq(ride_id, event, values)`. Los usuarios
  de la app no cambian.
- `notices.py` arma el mensaje (02, flujo 4) con los mismos valores (nombre, placa, monto) y agrega:
  - **Asignado**: crea el enlace en vivo con `safety` (`ride_share_links`) si el flag `share_live_link` está
    encendido, y envía el **PIN** con `_pin_for` cuando la ciudad lo exige.
  - **Terminado**: monto total y método de pago, y luego la lista de calificación.
- Chat (pregunta 4): `rides.events.emit_message` también encola el reenvío si el destinatario es de WhatsApp; los
  textos entrantes en estado `in_ride` llaman a `rides.services.post_message` con el usuario invitado.
- Los avisos al **motorizado** no cambian: push y app.

## Envío (`whatsapp.send`)
- Tarea con reintentos (3, espera exponencial) para errores de red y 5xx. Errores que no se reintentan:
  - `131047` (pasaron más de 24 h desde el último mensaje del usuario): se reemplaza por la plantilla
    correspondiente si existe (04) o se marca como no entregado.
  - `131026` (el número no puede recibir), `131051` (tipo no soportado), `100` (parámetro inválido): se registran
    y alertan.
  - `130429` / `131056` (límite de envío del número o del par empresa-usuario): reintento con espera y se agrupan
    mensajes (un aviso de estado en vez de varios seguidos).
- Al recibir un mensaje se marca como **leído** (`status: read`) y se muestra el indicador de «escribiendo»
  mientras se procesa, para que el pasajero sepa que el bot lo vio.
- Cada envío se registra en `whatsapp_messages` con el `wamid` devuelto; `process_status` actualiza `sent`,
  `delivered`, `read` o `failed`.
- Cliente HTTP compartido (como `geo.clients.http()`), timeout de 10 s, versión de la Graph API fija por variable
  (`WHATSAPP_GRAPH_VERSION`) para que un cambio de Meta no rompa nada sin aviso.

## Soporte humano (decidido 11)
- Nuevo valor `ReportSource.WHATSAPP` (migración del enum `report_source`).
- Abrir soporte crea un `Report` del invitado (o del cliente) y pone el contacto en modo `support`; cada mensaje
  entrante se agrega como `ReportMessage` de autor `user`. Las fotos se descargan con la Media API
  (`GET /{media-id}` → URL temporal → descarga con el token), se les quita el EXIF como a las demás fotos y se
  guardan en el S3 privado.
- Cuando el equipo responde desde el admin, `support.conversation` notifica al usuario. Hoy lo hace por push o
  email; se agrega WhatsApp para los tickets con `source = whatsapp` (dentro de la ventana: texto libre; fuera:
  plantilla `soporte_respuesta`).
- Cerrar el ticket envía el mensaje de cierre y saca al contacto del modo `support`.

## Datos
### Tablas nuevas
**`whatsapp_contacts`**
| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | uuid | |
| `wa_id` | varchar(20), único | Número en formato de WhatsApp (solo dígitos, con código de país) |
| `phone` | varchar(16) | E.164 con `+` |
| `profile_name` | varchar(100) | Nombre de perfil, solo informativo |
| `user_id` | FK `users`, null, `SET NULL` | El invitado o cliente ligado |
| `consent_at`, `consent_version` | timestamptz, varchar | Aceptó términos al escribir (doc 07) |
| `last_inbound_at` | timestamptz | Abre la ventana de 24 h (04) |
| `last_payment_method` | enum `payment_method`, null | Para «igual que la vez pasada» |
| `blocked_at`, `blocked_reason`, `blocked_by_id` | | Bloqueo desde el admin o automático (05) |
| `created_at`, `updated_at` | | |

**`whatsapp_messages`** (registro, retención 90 días con `purge_messages` diario)
| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | uuid | |
| `wamid` | varchar(128), único, null | Id de Meta |
| `contact_id` | FK `whatsapp_contacts` | |
| `direction` | `in` / `out` | |
| `kind` | varchar(30) | `text`, `location`, `interactive`, `template`, `image`… |
| `text` | varchar(1000), null | Texto visible, recortado; nunca tokens |
| `payload` | jsonb | Solo lo necesario (ids de botón, coordenadas redondeadas a 5 decimales) |
| `ride_id`, `report_id` | FK, null | Para soporte |
| `status` | `received`, `sent`, `delivered`, `read`, `failed` | |
| `error_code` | integer, null | |
| `created_at` | | Índice `(contact_id, created_at)` |

### Cambios en tablas existentes
- `users`: `is_guest` (bool, default false), `signup_source` (`app` / `whatsapp`, default `app`), `phone`
  (varchar(16), único parcial donde no es null), `customer_since` (timestamptz, null; se llena en el primer viaje
  completado para **todos** los pasajeros, así «cliente» significa lo mismo en ambos canales).
- `rides`: `channel` (`app` / `whatsapp`, default `app`) para métricas y para la etiqueta del motorizado.
- `report_source`: valor `whatsapp`.
- Migraciones con `alembic upgrade head` y `alembic check` como siempre; todas aditivas, sin bloqueos largos.

### Redis
| Clave | Uso | TTL |
| --- | --- | --- |
| `wa:conv:{wa_id}` | Estado de la conversación | Según estado |
| `wa:seen:{wamid}` | Deduplicar reintentos de Meta | 48 h |
| `wa:lock:{wa_id}` | Orden por número | 30 s |
| `wa:rl:{wa_id}:{ventana}` | Límites por número (05) | 1 min / 1 h / 1 día |
| `wa:guest:{user_id}` | Caché «este usuario es de WhatsApp» para el enrutamiento de avisos | 1 h |

## Cambios fuera de la API
- **App del motorizado**: la oferta y el viaje activo muestran la etiqueta «Pedido por WhatsApp» cuando
  `channel == "whatsapp"` (campo nuevo en la serialización; textos en `es` y `en` como exige la app). No ve el
  teléfono (pregunta 3).
- **Admin**:
  - Página **WhatsApp**: contactos (buscar por número o nombre, filtro bloqueados / invitados / clientes),
    conversación de cada contacto (lectura auditada, doc 06), bloquear y desbloquear, enlace a sus viajes y
    tickets. Permiso: rol Soporte.
  - **Tickets**: etiqueta de origen WhatsApp y respuesta que sale por WhatsApp.
  - **Clientes / CRM** (doc 24): filtro por origen y columna «cliente desde».
  - **Métricas**: mensajes in/out por día, cotizaciones, viajes pedidos y completados por WhatsApp, errores de
    envío, calidad del número.
  - Textos en `i18n/locales/{es,en}.json` (el admin sigue bilingüe; solo el bot es en español).
- **Control remoto**: flag `whatsapp_rides` (apagado por defecto). Apagado, el bot responde un único mensaje
  amable con el enlace de descarga de la app y el soporte sigue funcionando.

## Capacidad
Una persona pidiendo un viaje genera unos 12 mensajes entrantes y 15 salientes. Con 1000 viajes diarios por
WhatsApp son unos 27 000 mensajes al día, unos pocos por segundo en hora pico: muy por debajo del límite de la
Cloud API (80 mensajes por segundo por número, ampliable) y de la capacidad de la API medida el 2026-10-25
(~260 req/s). El trabajo pesado (ruta OSRM, cotización) ya se hace hoy para la app.
