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
2. ¿Número de WhatsApp de soporte? Recomendado: uno dedicado, configurable.
