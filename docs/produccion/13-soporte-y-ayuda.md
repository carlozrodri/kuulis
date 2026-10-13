# 13 · Soporte y centro de ayuda

**Prioridad:** P0 · **Área:** Mobile · API · Admin · **Depende de:** 06

## Objetivo
Que el usuario resuelva solo lo común (centro de ayuda) y que cuando escriba a Kuulis tenga una conversación
de ida y vuelta con el equipo, con tiempos de respuesta medidos. Reducir la carga del equipo con respuestas
guardadas y flujos guiados (objeto perdido, cobro incorrecto).

## Estado actual
- Reportes (`/reports`) por viaje o generales, con categorías, prioridad, notas internas, asignación y una
  **respuesta final única** al resolver (`resolution`). El usuario no puede añadir información después ni el
  equipo puede pedírsela.
- No hay centro de ayuda ni preguntas frecuentes.
- No hay forma de contactar a Kuulis sin cuenta (por ejemplo, un motorizado que no puede entrar).
- Objeto perdido es una categoría más, sin flujo para poner en contacto a las partes tras el viaje (el chat se
  cierra al completar).

## Alcance
### Incluye
1. **Conversación en cada reporte** (convertirlo en ticket): mensajes del usuario y del equipo con adjuntos
   (fotos), estado "esperando tu respuesta", notificación push en cada respuesta, cierre automático si el usuario
   no responde en 7 días.
2. **Centro de ayuda** in-app y en la web (08): artículos en es/en por tema (cuenta, pagos al motorizado,
   billetera y cuota, seguridad, documentos, problemas con la app), buscador, "¿Te ayudó?" y botón "Contactar"
   que crea el ticket con el artículo como contexto.
3. **Flujos guiados** desde el detalle del viaje:
   - **Objeto perdido**: el pasajero describe el objeto; se notifica al motorizado, que responde "Lo tengo" /
     "No lo tengo"; si lo tiene, se abre un chat temporal de 72 h entre ambos (con el chat existente) para
     coordinar la entrega.
   - **Cobro distinto al de la app**: muestra el precio congelado y abre ticket con prioridad normal.
   - **El motorizado no llegó / el pasajero no se presentó**: enlaza con las reglas de 15.
4. **Contacto sin cuenta**: formulario en la web (08) con email y captcha autoalojado (por ejemplo, desafío
   de prueba de trabajo sin terceros), que crea un ticket ligado al email.
5. **Herramientas del equipo**: respuestas guardadas con variables (`{nombre}`, `{viaje}`), macros (responder +
   cambiar estado + etiqueta), etiquetas, SLA por prioridad (urgente 15 min, normal 24 h) con indicador de
   vencidos, asignación automática por rol o reparto equitativo, vista "mis tickets".
6. **Satisfacción** (CSAT): al cerrar, el usuario califica la atención de 1 a 5.
7. **Canal externo opcional**: botón de WhatsApp de soporte configurable desde 10 (sin integración, abre el chat
   con el número de Kuulis), para quien lo prefiera.

### Fuera
- Integración con la API de WhatsApp Business (costo por conversación).
- Chat en vivo con agentes en tiempo real (el ticket con push es suficiente al lanzar).

## App móvil
### Pasajero y motorizado
- Perfil → **Ayuda**: buscador, temas, artículos, "Mis reportes" (ya existe, pasa a "Mis conversaciones").
- Detalle de un reporte: hilo de mensajes, campo para responder, adjuntar foto, estado y calificación al cerrar.
- Detalle del viaje: "Necesito ayuda con este viaje" con los flujos guiados.
### Motorizado
- Notificación de objeto perdido con respuesta rápida "Lo tengo / No lo tengo".

## Admin
- La bandeja de reportes pasa a ser **Soporte**: vista de conversación, respuestas guardadas, macros, etiquetas,
  SLA, filtros por "esperando al equipo" / "esperando al usuario", "mis tickets".
- **Centro de ayuda**: editor de artículos (Markdown es/en), orden por tema, publicar/ocultar, estadísticas de
  vistas y de "¿Te ayudó?".
- **Respuestas guardadas**: gestión por el equipo.
- Métricas de soporte: tickets por día, tiempo a primera respuesta, tiempo de resolución, CSAT, por agente.

## API y datos
- `report_messages` (`report_id`, `author_id`, `author_kind` user|staff|system, `body`, `attachments` keys,
  `created_at`). Las notas internas actuales siguen en `report_notes`.
- `reports` agrega `waiting_on` (staff|user), `first_response_at`, `sla_due_at`, `tags` text[], `csat`,
  `source` (app|web|lost_item_flow), `contact_email` (sin cuenta).
- `help_articles` (`slug`, `topic`, `title`, `body_md`, `locale`, `published`, `position`, `views`,
  `helpful_yes`, `helpful_no`). `canned_responses` (`title`, `body`, `locale`, `created_by`).
- `lost_item_requests` (`ride_id`, `description`, `driver_answer`, `chat_until`).
- Endpoints: `GET/POST /reports/{id}/messages`, `POST /reports/{id}/csat`, `GET /help/articles?locale&q`,
  `POST /help/articles/{id}/feedback`, `POST /public/contact`, `POST /rides/{id}/lost-item`,
  `POST /rides/{id}/lost-item/answer`; admin: CRUD de artículos y respuestas guardadas, mensajes, macros.
- El chat del viaje acepta mensajes en estado `completed` si existe `lost_item_requests.chat_until` vigente.
- Notificaciones `kind: "support"` con `data.report_id` (abre el hilo al tocarla, ver 14).

## Criterios de aceptación
- Un usuario puede responder a una pregunta del equipo dentro del mismo reporte y recibe push de cada respuesta.
- Un pasajero que olvidó algo puede ponerse en contacto con el motorizado tras el viaje sin compartir teléfonos.
- Un ticket urgente sin respuesta en 15 min se marca vencido y alerta (03).
- Los artículos se pueden editar desde el admin y aparecen en la app y la web sin publicar código.
- Alguien sin cuenta puede escribir a soporte desde la web y recibir la respuesta por email.

## Dependencias
06 (rol `soporte`). 14 para abrir el hilo al tocar la notificación. 08 para el formulario y la ayuda pública.

## Preguntas para Carlos
1. ¿Quién atenderá el soporte al inicio y en qué horario? Define los SLA visibles al usuario.
   **Abierta.** Mientras tanto: SLA interno urgente 15 min y normal 24 h, y la promesa visible "Respondemos en
   menos de 24 horas" (editable en Ajustes → Soporte).
2. ¿Número de WhatsApp de soporte? Recomendado: uno dedicado, configurable. **Decidido** (recomendado):
   configurable en Ajustes (`app_links.support_whatsapp`); el botón aparece solo cuando hay número.

## Cómo quedó (2026-10-13)
### API (`api/apps/support`, conversación en `apps/moderation`)
- **Conversación en cada reporte:** `report_messages` (usuario, equipo o sistema, con hasta 4 fotos). La
  descripción es el primer mensaje; la migración convierte los reportes existentes (descripción y resolución).
  `reports` suma `waiting_on`, `sla_due_at`, `first_response_at`, `tags`, `csat`, `source`, `contact_email`,
  `user_seen_at` (punto de "nueva respuesta"). Cada respuesta del equipo manda push (`type: support`) o email
  para tickets de la web. Responder un ticket resuelto hace menos de `auto_close_days` (7) lo reabre.
- **Tiempos de respuesta:** urgente 15 min, normal 24 h (`support.*`). Vencidos marcados en el admin; los
  urgentes vencidos avisan una vez por Telegram (03). Un ticket que espera al usuario 7 días se cierra solo con
  un mensaje y se puede seguir respondiendo. Tarea `support_sla` cada minuto con latido en Sistema.
- **Equipo:** respuestas guardadas con `{nombre}` y `{viaje}`, que funcionan como macros (responder + esperar
  al usuario o resolver + etiquetas); filtros esperando al equipo / al usuario, mis tickets, sin asignar,
  vencidos, etiqueta y origen; asignación automática opcional (`support.auto_assign`) al de menos tickets;
  métricas (`/admin/support/metrics`); CSAT de 1 a 5 al cerrar.
- **Centro de ayuda:** `help_articles` por idioma, tema y público (pasajero/motorizado), con vistas y "¿Te
  ayudó?". Permiso nuevo `help.manage` (lo tiene el rol Soporte). La migración carga 9 artículos iniciales en
  español e inglés.
- **Objeto perdido:** `POST /rides/{id}/lost-item` (hasta `lost_item_days`, 7) abre ticket y avisa al
  motorizado; "Lo tengo" reabre el chat del viaje por `lost_item_chat_hours` (72) sin compartir teléfonos.
- **Contacto sin cuenta:** `POST /public/contact` con prueba de trabajo propia (sin terceros, dificultad 16
  bits, un solo uso) y respuesta por email con `reply_to` al correo de soporte.
- Auditoría nueva: `report.message`, `canned.*`, `help.*`.

### Admin
- "Soporte" con colas, contadores, SLA, etiquetas, origen y CSAT; ficha como conversación con compositor
  (respuestas guardadas, fotos, qué hacer después de enviar), etiquetas, contexto del artículo y del objeto
  perdido. Páginas Respuestas guardadas, Métricas de soporte y Centro de ayuda (editor Markdown con vista
  previa). Bloque Soporte en Ajustes.

### App
- Ajustes → Ayuda: buscador, temas, artículos con "¿Te ayudó?", Mis conversaciones con punto de no leído,
  WhatsApp y email cuando están configurados. Hilo de cada reporte con fotos y calificación al cerrar.
- Detalle del viaje → "Necesito ayuda con este viaje": olvidé un objeto, me cobraron distinto, no llegó / no se
  presentó y otro problema. El motorizado responde "Lo tengo / No lo tengo" y el chat se abre tras el viaje.

### Web
- `/ayuda`, `/ayuda/{slug}` y `/contacto` (formulario con la verificación propia), enlazados en el menú.

### Pendiente
- Quién atiende y en qué horario (pregunta 1).
- Botones "Lo tengo / No lo tengo" en la propia notificación (hoy están en la pantalla que abre).
